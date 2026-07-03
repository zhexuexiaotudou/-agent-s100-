# Evidence export checklist

Required raw subset for GPT Pro review:

- [ ] BPU full-chain raw final logits `.npy`
- [ ] BPU full-chain dequant final logits `.npy`
- [ ] GGUF last-logits `.npy`
- [ ] BPU seg26 raw output `.npy`
- [ ] BPU seg26 dequant output `.npy`
- [ ] isolated seg27_28 synthetic hidden input `.npy`
- [ ] isolated seg27_28 synthetic output `.npy`
- [ ] isolated seg27_28 real_bpu_seg26 input `.npy`
- [ ] isolated seg27_28 real_bpu_seg26 output `.npy`
- [ ] representative input sweep variants `.npy`
- [ ] `RAW_EVIDENCE_SUBSET_MANIFEST.json`
- [ ] `MANIFEST.json`
- [ ] `SHA256SUMS.txt`
