#include "diffuse.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static void usage(const char * prog) {
    std::fprintf(stderr,
        "Usage: %s -m MODEL [-t THREADS] [-s STEPS] [--temp F] "
        "[--seed INT] [--remasking entropy_exit|low_confidence|maskgit_plus|topk_margin|random] "
        "[--cache-keep-active INT]\n\n"
        "stdin protocol:\n"
        "  GEN<TAB>request_id<TAB>n_generate<TAB>n_steps<TAB>seed<TAB>token_csv\n"
        "  QUIT\n\n"
        "stdout protocol:\n"
        "  OK<TAB>request_id<TAB>elapsed_ms<TAB>token_csv\n"
        "  ERR<TAB>request_id<TAB>message\n",
        prog);
}

static std::vector<int32_t> parse_tokens(const std::string & str) {
    std::vector<int32_t> out;
    const char * p = str.c_str();
    while (*p) {
        out.push_back(std::atoi(p));
        while (*p && *p != ',') p++;
        if (*p == ',') p++;
    }
    return out;
}

static std::vector<std::string> split_tabs(const std::string & line) {
    std::vector<std::string> parts;
    std::string item;
    std::istringstream in(line);
    while (std::getline(in, item, '\t')) {
        parts.push_back(item);
    }
    return parts;
}

static const char * remasking_name(diffuse_remasking value) {
    switch (value) {
        case diffuse_remasking::ENTROPY_EXIT: return "entropy_exit";
        case diffuse_remasking::LOW_CONFIDENCE: return "low_confidence";
        case diffuse_remasking::MASKGIT_PLUS: return "maskgit_plus";
        case diffuse_remasking::TOPK_MARGIN: return "topk_margin";
        case diffuse_remasking::RANDOM: return "random";
    }
    return "unknown";
}

static diffuse_remasking parse_remasking(const char * value) {
    if (std::strcmp(value, "entropy_exit") == 0) return diffuse_remasking::ENTROPY_EXIT;
    if (std::strcmp(value, "maskgit_plus") == 0) return diffuse_remasking::MASKGIT_PLUS;
    if (std::strcmp(value, "topk_margin") == 0) return diffuse_remasking::TOPK_MARGIN;
    if (std::strcmp(value, "random") == 0) return diffuse_remasking::RANDOM;
    return diffuse_remasking::LOW_CONFIDENCE;
}

int main(int argc, char ** argv) {
    std::string model_path;
    int n_threads = 4;
    int default_steps = 4;
    float temperature = 0.0f;
    uint32_t default_seed = 42;
    float entropy_threshold = 1.5f;
    diffuse_remasking remasking = diffuse_remasking::ENTROPY_EXIT;
    int cache_keep_active = 2;

    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "-m") == 0 && i + 1 < argc) {
            model_path = argv[++i];
        } else if (std::strcmp(argv[i], "-t") == 0 && i + 1 < argc) {
            n_threads = std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "-s") == 0 && i + 1 < argc) {
            default_steps = std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "--temp") == 0 && i + 1 < argc) {
            temperature = std::atof(argv[++i]);
        } else if (std::strcmp(argv[i], "--seed") == 0 && i + 1 < argc) {
            default_seed = (uint32_t)std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "--entropy-threshold") == 0 && i + 1 < argc) {
            entropy_threshold = std::atof(argv[++i]);
        } else if (std::strcmp(argv[i], "--cache-keep-active") == 0 && i + 1 < argc) {
            cache_keep_active = std::atoi(argv[++i]);
        } else if (std::strcmp(argv[i], "--remasking") == 0 && i + 1 < argc) {
            remasking = parse_remasking(argv[++i]);
        } else if (std::strcmp(argv[i], "-h") == 0 || std::strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        }
    }

    if (model_path.empty()) {
        usage(argv[0]);
        return 2;
    }

    std::fprintf(stderr, "[resident] loading model: %s\n", model_path.c_str());
    auto load_start = std::chrono::steady_clock::now();
    diffuse_model * model = diffuse_model_load(model_path, n_threads);
    if (!model) {
        std::fprintf(stderr, "[resident] failed to load model\n");
        return 1;
    }
    auto load_end = std::chrono::steady_clock::now();
    double load_ms = std::chrono::duration<double, std::milli>(load_end - load_start).count();
    std::fprintf(stderr,
        "[resident] ready load_ms=%.1f threads=%d default_steps=%d remasking=%s cache_keep_active=%d\n",
        load_ms, n_threads, default_steps, remasking_name(remasking), cache_keep_active);
    std::cout << "READY\t" << (long long)load_ms << std::endl;

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        if (line == "QUIT") break;
        std::vector<std::string> parts = split_tabs(line);
        std::string request_id = parts.size() > 1 ? parts[1] : "unknown";
        if (parts.size() != 6 || parts[0] != "GEN") {
            std::cout << "ERR\t" << request_id << "\tbad_request" << std::endl;
            continue;
        }

        int n_generate = std::atoi(parts[2].c_str());
        int n_steps = std::atoi(parts[3].c_str());
        uint32_t seed = (uint32_t)std::atoi(parts[4].c_str());
        if (n_generate <= 0) n_generate = 16;
        if (n_steps <= 0) n_steps = default_steps;
        if (seed == 0) seed = default_seed;

        std::vector<int32_t> input_tokens = parse_tokens(parts[5]);
        if (input_tokens.empty()) {
            std::cout << "ERR\t" << request_id << "\tempty_tokens" << std::endl;
            continue;
        }

        int n_ctx = (int)input_tokens.size() + n_generate;
        diffuse_context * ctx = diffuse_context_new(model, n_ctx, n_threads);
        if (!ctx) {
            std::cout << "ERR\t" << request_id << "\tcontext_alloc_failed" << std::endl;
            continue;
        }

        diffuse_sampler_params params;
        params.n_steps = n_steps;
        params.temperature = temperature;
        params.seed = seed;
        params.schedule = diffuse_schedule::COSINE;
        params.remasking = remasking;
        params.entropy_threshold = entropy_threshold;
        params.use_cache = true;
        params.cache_refresh = 0;
        params.cache_keep_active = cache_keep_active;

        auto started = std::chrono::steady_clock::now();
        std::vector<int32_t> result = diffuse_generate(ctx, input_tokens, n_generate, params, nullptr);
        auto ended = std::chrono::steady_clock::now();
        diffuse_context_free(ctx);

        long long elapsed_ms = (long long)std::chrono::duration<double, std::milli>(ended - started).count();
        std::cout << "OK\t" << request_id << "\t" << elapsed_ms << "\t";
        for (size_t i = 0; i < result.size(); i++) {
            if (i > 0) std::cout << ",";
            std::cout << result[i];
        }
        std::cout << std::endl;
    }

    diffuse_model_free(model);
    std::fprintf(stderr, "[resident] stopped\n");
    return 0;
}
