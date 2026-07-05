# 140 Report Wording Fixes

| original | problem | recommended | reason |
| --- | --- | --- | --- |
| UI v2 is fully live on production | Prior packet used temp service; current /ui curl on 8765 needs fresh browser gate. | UI v2 `/ui` is reachable on 8765 and 18766 in current curl checks; fresh browser validation is pending. | Avoid overclaiming production rollout completeness. |
| Complete embedding RAG | Evidence is FTS-first with optional embedding. | Document Q&A uses local SQLite FTS-first retrieval; embedding/reranker are optional enhancements. | Avoid unsupported semantic-RAG claim. |
| Token cost dropped by 92.68% | Benchmark token reduction is not a bill. | 130-case benchmark shows 92.68% average cloud-input token reduction. | Avoid billing claim. |
| Arbitrary NAS copy/write is safe | Only bounded single-file copy is allowed. | Controlled copy requires preview/dry-run/confirmation/signed token/source rehash/target absent/dispatcher. | Avoid broad write claim. |
| Mobile app workflows complete | Only limited mobile screenshot evidence exists. | Mobile-responsive core views have screenshot evidence; full mobile workflow acceptance remains a follow-up. | Avoid full mobile production claim. |
| Dream7B is product capability | Dream7B remains research-only. | Dream7B has a 31-row truth set but stops at BPU operator alignment review. | Avoid product model claim. |
| Multimodal semantic index | Live status is metadata-first. | Multimodal NAS index covers metadata records; OCR/embedding/keyframe/transcript are default-off. | Avoid AI vision/audio overclaim. |
| Journal fully merged and rolled out | Live rollout and repo state differ. | Journal production package and S100P live rollout passed; repo remains dirty and needs submission cleanup. | Avoid repo-clean claim. |
