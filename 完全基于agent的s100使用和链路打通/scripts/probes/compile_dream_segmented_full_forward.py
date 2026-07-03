#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import torch
from hbdk4.compiler import leap, save

from leap_llm.nn.modules import (
    ConstFakeQuant,
    FakeQuantAdd,
    FakeQuantEmbedding,
    FakeQuantLinear,
    FakeQuantMatmul,
    FakeQuantMul,
    FakeQuantRMSNorm,
    FakeQuantSoftmax,
    FakeQuantSwish,
)
from leap_llm.nn.utils import Model, Module, load_safetensors_state_dict


@dataclass
class Args:
    hidden_size: int
    intermediate_size: int
    num_attention_heads: int
    num_hidden_layers: int
    num_key_value_heads: int
    vocab_size: int
    rms_norm_eps: float
    rope_theta: float
    max_position_embeddings: int
    head_dim: int
    w_bits: int = 8


class RotateHalf(Module):
    def __init__(self):
        super().__init__()
        self.mul = FakeQuantMul(quantized=True)

    def build(self, x):
        n_head, seq_len, head_dim = x.type.shape
        x1 = leap.slice(x, [0, 0, 0], [n_head, seq_len, head_dim // 2], [1, 1, 1])
        x2 = leap.slice(x, [0, 0, head_dim // 2], [n_head, seq_len, head_dim], [1, 1, 1])
        return leap.concat([self.mul(-1, x2), x1], 2)

    def forward(self, x):
        x1 = x[..., : x.shape[-1] // 2]
        x2 = x[..., x.shape[-1] // 2 :]
        return torch.cat((self.mul(-1, x2), x1), dim=-1)


class Rotary(Module):
    def __init__(self):
        super().__init__()
        self.rotate_q = RotateHalf()
        self.rotate_k = RotateHalf()
        self.q_cos = FakeQuantMul(quantized=True)
        self.q_sin = FakeQuantMul(quantized=True)
        self.q_add = FakeQuantAdd(quantized=True)
        self.k_cos = FakeQuantMul(quantized=True)
        self.k_sin = FakeQuantMul(quantized=True)
        self.k_add = FakeQuantAdd(quantized=True)
        self.q_fq = ConstFakeQuant(16)
        self.k_fq = ConstFakeQuant(16)

    def build(self, q, k, cos, sin):
        q = self.q_fq(q)
        k = self.k_fq(k)
        q_out = self.q_add(self.q_cos(q, cos), self.q_sin(self.rotate_q(q), sin))
        k_out = self.k_add(self.k_cos(k, cos), self.k_sin(self.rotate_k(k), sin))
        return q_out, k_out

    def forward(self, q, k, cos, sin):
        q = self.q_fq(q)
        k = self.k_fq(k)
        q_out = self.q_add(self.q_cos(q, cos), self.q_sin(self.rotate_q(q), sin))
        k_out = self.k_add(self.k_cos(k, cos), self.k_sin(self.rotate_k(k), sin))
        return q_out, k_out


class FullAttention(Module):
    def __init__(self, args: Args):
        super().__init__()
        self.hidden_size = args.hidden_size
        self.num_heads = args.num_attention_heads
        self.num_kv_heads = args.num_key_value_heads
        self.head_dim = args.head_dim
        self.groups = self.num_heads // self.num_kv_heads
        self.q_proj = FakeQuantLinear(args.hidden_size, self.num_heads * self.head_dim, bias=True, w_bits=args.w_bits)
        self.k_proj = FakeQuantLinear(args.hidden_size, self.num_kv_heads * self.head_dim, bias=True, w_bits=args.w_bits)
        self.v_proj = FakeQuantLinear(args.hidden_size, self.num_kv_heads * self.head_dim, bias=True, quant_bits=8, w_bits=args.w_bits)
        self.o_proj = FakeQuantLinear(self.num_heads * self.head_dim, args.hidden_size, bias=False, w_bits=args.w_bits)
        self.rotary = Rotary()
        self.qk = FakeQuantMatmul(8, 16)
        self.sv = FakeQuantMatmul(None, 8)
        self.scale = FakeQuantMul(quantized=False)
        self.softmax = FakeQuantSoftmax(quant_bits=16, quantized=True)

    def build(self, hidden, cos, sin):
        seq = hidden.type.shape[0]
        q = self.q_proj(hidden)
        k = self.k_proj(hidden)
        v = self.v_proj(hidden)
        q = leap.transpose(leap.reshape(q, [seq, self.num_heads, self.head_dim]), [1, 0, 2])
        k = leap.transpose(leap.reshape(k, [seq, self.num_kv_heads, self.head_dim]), [1, 0, 2])
        v = leap.transpose(leap.reshape(v, [seq, self.num_kv_heads, self.head_dim]), [1, 0, 2])
        q, k = self.rotary(q, k, cos, sin)
        k_t = leap.transpose(k, [0, 2, 1])
        q_g = leap.reshape(q, [self.num_kv_heads, self.groups * seq, self.head_dim])
        weights = self.qk(q_g, k_t)
        weights = leap.reshape(weights, [self.num_heads, seq, seq])
        weights = self.scale(weights, 1.0 / (self.head_dim ** 0.5))
        weights = self.softmax(weights)
        weights = leap.reshape(weights, [self.num_kv_heads, self.groups * seq, seq])
        out = self.sv(weights, v)
        out = leap.reshape(out, [self.num_heads, seq, self.head_dim])
        out = leap.transpose(out, [1, 0, 2])
        out = leap.reshape(out, [seq, self.num_heads * self.head_dim])
        return self.o_proj(out)

    def forward(self, hidden, cos, sin):
        seq = hidden.shape[0]
        q = self.q_proj(hidden).reshape(seq, self.num_heads, self.head_dim).transpose(1, 0)
        k = self.k_proj(hidden).reshape(seq, self.num_kv_heads, self.head_dim).transpose(1, 0)
        v = self.v_proj(hidden).reshape(seq, self.num_kv_heads, self.head_dim).transpose(1, 0)
        q, k = self.rotary(q, k, cos, sin)
        q_g = q.reshape(self.num_kv_heads, self.groups * seq, self.head_dim)
        weights = self.qk(q_g, k.transpose(1, 2)).reshape(self.num_heads, seq, seq)
        weights = self.scale(weights, 1.0 / (self.head_dim ** 0.5))
        weights = self.softmax(weights)
        out = self.sv(weights.reshape(self.num_kv_heads, self.groups * seq, seq), v)
        return self.o_proj(out.reshape(self.num_heads, seq, self.head_dim).transpose(1, 0).reshape(seq, self.num_heads * self.head_dim))


class FullBlock(Module):
    def __init__(self, args: Args):
        super().__init__()
        self.input_layernorm = FakeQuantRMSNorm(args.hidden_size, eps=args.rms_norm_eps)
        self.post_attention_layernorm = FakeQuantRMSNorm(args.hidden_size, eps=args.rms_norm_eps)
        self.self_attn = FullAttention(args)
        self.gate_proj = FakeQuantLinear(args.hidden_size, args.intermediate_size, bias=False, w_bits=args.w_bits)
        self.up_proj = FakeQuantLinear(args.hidden_size, args.intermediate_size, bias=False, w_bits=args.w_bits)
        self.down_proj = FakeQuantLinear(args.intermediate_size, args.hidden_size, bias=False, w_bits=args.w_bits)
        self.act = FakeQuantSwish(True, 16)
        self.mlp_mul = FakeQuantMul(quantized=False)
        self.add_attn = FakeQuantAdd(quantized=True)
        self.add_mlp = FakeQuantAdd(quantized=True)

    def build(self, hidden, cos, sin):
        residual = hidden
        hidden = self.input_layernorm(hidden)
        hidden = self.self_attn(hidden, cos, sin)
        hidden = self.add_attn(residual, hidden)
        residual = hidden
        hidden = self.post_attention_layernorm(hidden)
        hidden = self.down_proj(self.mlp_mul(self.act(self.gate_proj(hidden)), self.up_proj(hidden)))
        return self.add_mlp(residual, hidden)

    def forward(self, hidden, cos, sin):
        residual = hidden
        hidden = self.input_layernorm(hidden)
        hidden = self.self_attn(hidden, cos, sin)
        hidden = self.add_attn(residual, hidden)
        residual = hidden
        hidden = self.post_attention_layernorm(hidden)
        hidden = self.down_proj(self.mlp_mul(self.act(self.gate_proj(hidden)), self.up_proj(hidden)))
        return self.add_mlp(residual, hidden)


class DreamFullForward(Model):
    def __init__(self, args: Args, seq_len: int):
        super().__init__()
        self.args = args
        self.seq_len = seq_len
        self.embed_tokens = FakeQuantEmbedding(args.vocab_size, args.hidden_size)
        self.layers = torch.nn.ModuleList([FullBlock(args) for _ in range(args.num_hidden_layers)])
        self.norm = FakeQuantRMSNorm(args.hidden_size, eps=args.rms_norm_eps)
        self.lm_head = FakeQuantLinear(args.hidden_size, args.vocab_size, bias=False, w_bits=args.w_bits)
        inv_freq = 1.0 / (args.rope_theta ** (torch.arange(0, args.head_dim, 2, dtype=torch.int64).float() / args.head_dim))
        t = torch.arange(args.max_position_embeddings, dtype=torch.int64).type_as(inv_freq)
        freqs = torch.outer(t, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self.cos = emb.cos().to(torch.float32)[:seq_len, :]
        self.sin = emb.sin().to(torch.float32)[:seq_len, :]
        self.cos_fq = ConstFakeQuant(16)
        self.sin_fq = ConstFakeQuant(16)

    def build(self, tokens, position_ids):
        _bsz, seq = tokens.type.shape
        tokens = leap.reshape(tokens, [seq, _bsz])
        hidden = leap.reshape(self.embed_tokens(tokens), [seq, self.args.hidden_size])
        position_ids = leap.reshape(position_ids, [seq, _bsz])
        cos = leap.reshape(leap.gather_nd(self.cos, position_ids, 0), [1, seq, self.args.head_dim])
        sin = leap.reshape(leap.gather_nd(self.sin, position_ids, 0), [1, seq, self.args.head_dim])
        cos = self.cos_fq(cos)
        sin = self.sin_fq(sin)
        for layer in self.layers:
            hidden = layer(hidden, cos, sin)
        hidden = self.norm(hidden)
        hidden = leap.reshape(hidden, [1, seq, self.args.hidden_size])
        return self.lm_head(hidden)

    def forward(self, tokens, position_ids):
        _bsz, seq = tokens.shape
        hidden = self.embed_tokens(tokens.reshape(seq))
        cos = self.cos[position_ids.reshape(seq)].reshape(1, seq, self.args.head_dim)
        sin = self.sin[position_ids.reshape(seq)].reshape(1, seq, self.args.head_dim)
        cos = self.cos_fq(cos)
        sin = self.sin_fq(sin)
        for layer in self.layers:
            hidden = layer(hidden, cos, sin)
        hidden = self.norm(hidden)
        hidden = hidden.reshape(1, seq, self.args.hidden_size)
        return self.lm_head(hidden)


class DreamSegmentForward(Model):
    def __init__(self, args: Args, seq_len: int, layer_count: int, include_embed: bool, include_head: bool):
        super().__init__()
        self.args = args
        self.seq_len = seq_len
        self.include_embed = include_embed
        self.include_head = include_head
        if include_embed:
            self.embed_tokens = FakeQuantEmbedding(args.vocab_size, args.hidden_size)
        self.layers = torch.nn.ModuleList([FullBlock(args) for _ in range(layer_count)])
        if include_head:
            self.norm = FakeQuantRMSNorm(args.hidden_size, eps=args.rms_norm_eps)
            self.lm_head = FakeQuantLinear(args.hidden_size, args.vocab_size, bias=False, w_bits=args.w_bits)
        inv_freq = 1.0 / (args.rope_theta ** (torch.arange(0, args.head_dim, 2, dtype=torch.int64).float() / args.head_dim))
        t = torch.arange(args.max_position_embeddings, dtype=torch.int64).type_as(inv_freq)
        freqs = torch.outer(t, inv_freq)
        emb = torch.cat((freqs, freqs), dim=-1)
        self.cos = emb.cos().to(torch.float32)[:seq_len, :]
        self.sin = emb.sin().to(torch.float32)[:seq_len, :]
        self.cos_fq = ConstFakeQuant(16)
        self.sin_fq = ConstFakeQuant(16)

    def _cos_sin_build(self, position_ids, seq):
        position_ids = leap.reshape(position_ids, [seq, 1])
        cos = leap.reshape(leap.gather_nd(self.cos, position_ids, 0), [1, seq, self.args.head_dim])
        sin = leap.reshape(leap.gather_nd(self.sin, position_ids, 0), [1, seq, self.args.head_dim])
        return self.cos_fq(cos), self.sin_fq(sin)

    def _cos_sin_forward(self, position_ids, seq):
        cos = self.cos[position_ids.reshape(seq)].reshape(1, seq, self.args.head_dim)
        sin = self.sin[position_ids.reshape(seq)].reshape(1, seq, self.args.head_dim)
        return self.cos_fq(cos), self.sin_fq(sin)

    def build(self, x, position_ids):
        if self.include_embed:
            _bsz, seq = x.type.shape
            tokens = leap.reshape(x, [seq, _bsz])
            hidden = leap.reshape(self.embed_tokens(tokens), [seq, self.args.hidden_size])
        else:
            seq = x.type.shape[0]
            hidden = x
        cos, sin = self._cos_sin_build(position_ids, seq)
        for layer in self.layers:
            hidden = layer(hidden, cos, sin)
        if self.include_head:
            hidden = self.norm(hidden)
            hidden = leap.reshape(hidden, [1, seq, self.args.hidden_size])
            return self.lm_head(hidden)
        return hidden

    def forward(self, x, position_ids):
        if self.include_embed:
            _bsz, seq = x.shape
            hidden = self.embed_tokens(x.reshape(seq)).reshape(seq, self.args.hidden_size)
        else:
            seq = x.shape[0]
            hidden = x
        cos, sin = self._cos_sin_forward(position_ids, seq)
        for layer in self.layers:
            hidden = layer(hidden, cos, sin)
        if self.include_head:
            hidden = self.norm(hidden)
            hidden = hidden.reshape(1, seq, self.args.hidden_size)
            return self.lm_head(hidden)
        return hidden

def make_args(config: dict, seq_len: int, w_bits: int) -> Args:
    hidden = int(config["hidden_size"])
    heads = int(config["num_attention_heads"])
    return Args(
        hidden_size=hidden,
        intermediate_size=int(config["intermediate_size"]),
        num_attention_heads=heads,
        num_hidden_layers=int(config["num_hidden_layers"]),
        num_key_value_heads=int(config["num_key_value_heads"]),
        vocab_size=int(config["vocab_size"]),
        rms_norm_eps=float(config.get("rms_norm_eps", 1e-6)),
        rope_theta=float(config.get("rope_theta", 1000000.0)),
        max_position_embeddings=max(int(config.get("max_position_embeddings", seq_len)), seq_len),
        head_dim=int(config.get("head_dim", hidden // heads)),
        w_bits=w_bits,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--march", default="nash-e")
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--dtype", choices=["float32", "float16"], default="float32")
    parser.add_argument("--layers", type=int, default=0, help="Override layer count for probes; 0 keeps config.")
    parser.add_argument("--segment-start", type=int, default=0)
    parser.add_argument("--segment-end", type=int, default=0, help="Exclusive; 0 disables segmented mode.")
    ns = parser.parse_args()

    model_dir = Path(ns.model_dir)
    output_dir = Path(ns.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    total_layers = int(config["num_hidden_layers"])
    segmented = ns.segment_end > 0
    if segmented:
        config["num_hidden_layers"] = ns.segment_end - ns.segment_start
    elif ns.layers:
        config["num_hidden_layers"] = ns.layers
    args = make_args(config, ns.seq_len, ns.w_bits)
    if segmented:
        model = DreamSegmentForward(
            args,
            ns.seq_len,
            layer_count=ns.segment_end - ns.segment_start,
            include_embed=ns.segment_start == 0,
            include_head=ns.segment_end == total_layers,
        )
    else:
        model = DreamFullForward(args, ns.seq_len)
    state = load_safetensors_state_dict(str(model_dir))
    state = {
        key.replace(".mlp.gate_proj.", ".gate_proj.")
        .replace(".mlp.up_proj.", ".up_proj.")
        .replace(".mlp.down_proj.", ".down_proj."): value
        for key, value in state.items()
    }
    if segmented:
        keep = {}
        for key, value in state.items():
            if key.startswith("layers."):
                old_layer_id = int(key.split(".", 2)[1])
                if old_layer_id < ns.segment_start or old_layer_id >= ns.segment_end:
                    continue
                key = key.replace(f"layers.{old_layer_id}.", f"layers.{old_layer_id - ns.segment_start}.", 1)
            elif key.startswith(("embed_tokens.",)):
                if ns.segment_start != 0:
                    continue
            elif key.startswith(("norm.", "lm_head.")):
                if ns.segment_end != total_layers:
                    continue
            keep[key] = value
        state = keep
    elif ns.layers:
        keep = {}
        for key, value in state.items():
            if key.startswith("layers."):
                layer_id = int(key.split(".", 2)[1])
                if layer_id >= ns.layers:
                    continue
            keep[key] = value
        state = keep
    needs_lm_head = (not segmented) or (ns.segment_end == total_layers)
    if needs_lm_head and "lm_head.weight" not in state:
        state["lm_head.weight"] = state["embed_tokens.weight"]
    model.load_state_dict(state, strict=True)
    print("Model load state_dict success.")
    if ns.dtype == "float16":
        model.to(dtype=torch.float16)
    model.compile_mode(False)
    model.eval()
    with torch.no_grad():
        if segmented and ns.segment_start != 0:
            tokens = torch.zeros((ns.seq_len, args.hidden_size), dtype=torch.float32)
        else:
            tokens = torch.zeros((1, ns.seq_len), dtype=torch.long)
        position_ids = torch.arange(ns.seq_len, dtype=torch.long)
        _ = model(tokens, position_ids)
    model.compile_mode(True)
    if segmented and ns.segment_start != 0:
        inputs = [
            leap.TensorType([ns.seq_len, args.hidden_size], leap.float32),
            leap.TensorType([ns.seq_len], leap.int32),
        ]
    else:
        inputs = [
            leap.TensorType([1, ns.seq_len], leap.int32),
            leap.TensorType([ns.seq_len], leap.int32),
        ]
    name = (
        f"dream_segment_{ns.segment_start:02d}_{ns.segment_end:02d}"
        if segmented
        else "dream_full_forward"
    )
    suffix = (
        f"segment_{ns.segment_start}_{ns.segment_end}_seq{ns.seq_len}_q{ns.w_bits}"
        if segmented
        else f"full_forward_seq{ns.seq_len}_q{ns.w_bits}"
    )
    bc_path = output_dir / f"dream7b_{suffix}.bc"
    bc_module = model.export_module(inputs, name, str(bc_path))
    print("BC:", bc_path)
    converted_path = output_dir / f"dream7b_{suffix}_convert.bc"
    mlir = model.convert_mlir(bc_module, str(converted_path), enable_vpu=True, march=ns.march)
    print("Converted:", converted_path)
    func = mlir.functions[0]
    func.remove_io_op(["Dequantize", "Quantize"])
    removed_path = output_dir / f"dream7b_{suffix}_convert_removed.bc"
    save(mlir, str(removed_path))
    print("Converted removed:", removed_path)
    hbo_path = output_dir / f"dream7b_{suffix}.hbo"
    model.compile_hbo(mlir, str(hbo_path), march=ns.march)
    print("HBO:", hbo_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
