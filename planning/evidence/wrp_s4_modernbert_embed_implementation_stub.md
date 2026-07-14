# S4 implementation stub — `modernbert_embed` (future PR only)

**Status:** STUB / design note  
**HUMAN decision:** approved for future opt-in implementation PR (`planning/evidence/wrp_s4_modernbert_embed_decision.json`)  
**Runtime today:** hash embed default; ModernBERT env opt-in fail-closed; `s4_promoted=false`

## Allowed future PR scope (opt-in, M1-safe)

1. Keep **HashingEmbedder** as default for `resolve_embedder()`.  
2. Strengthen opt-in path docs/tests (env + provider import fail-closed).  
3. Memory footprint notes for M1 16GB; no auto-download as default.  
4. **Do not** make ModernBERT product default; **do not** bulk S4; **do not** touch S3.

## Out of scope for first impl PR

- ANN/HNSW as CORE recall truth  
- Cloud embedding providers as default  
- Engine start from doctor  

## Rollback

Unset ModernBERT env; hash path remains; supersede only via HUMAN lineage.
