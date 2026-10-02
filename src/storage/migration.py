"""Explicit legacy migration: model, dimensions and input text must all be proven."""
import json
import math
import pickle
from pathlib import Path


def trusted_vectors(index_dir,model,dimensions):
    root=Path(index_dir)
    meta=json.loads((root/'index_meta.json').read_text())
    if meta.get('embedding_model')!=model or meta.get('evidence_revision')!=1:
        raise ValueError('Legacy embedding/evidence provenance is unverifiable; rebuild from raw objects and verified caches')
    import chromadb
    from src.core.models import DocumentChunk
    # Trusted local pickle only; never accept uploaded pickle files.
    chunks=[DocumentChunk.model_validate(c.model_dump()) for c in pickle.loads((root/'children.pkl').read_bytes())]
    collection=chromadb.PersistentClient(path=str(root/'chroma')).get_collection(meta['collection'])
    rows=collection.get(include=['embeddings','documents'])
    lookup={cid:(text,vector) for cid,text,vector in zip(rows['ids'],rows['documents'],rows['embeddings'])}
    if len(lookup)!=len(chunks):
        raise ValueError('Vector store and chunk count differ')
    vectors={}
    for chunk in chunks:
        text=chunk.retrieval_text or chunk.text
        stored,vector=lookup.get(chunk.chunk_id,(None,[]))
        if stored!=text or len(vector)!=dimensions or not all(math.isfinite(float(x)) for x in vector):
            raise ValueError('Vector/input profile mismatch')
        vectors[text]=[float(x) for x in vector]
    return meta,vectors


class ReusedEmbeddings:
    def __init__(self,known,fallback):
        self.known,self.fallback=known,fallback
    def embed_query(self,text):
        return self.fallback.embed_query(text)
    def embed_documents(self,texts):
        missing=list(dict.fromkeys(t for t in texts if t not in self.known))
        if missing:
            self.known.update(zip(missing,self.fallback.embed_documents(missing)))
        return [self.known[t] for t in texts]
