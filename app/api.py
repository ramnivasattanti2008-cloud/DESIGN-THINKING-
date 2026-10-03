# -*- coding: utf-8 -*-
"""
BHARAT-SCAM-X HTTP API.

  POST /analyze   {"text": "..."}              -> full analysis
  POST /batch     {"texts": ["...", "..."]}    -> list of analyses
  GET  /health                                 -> model info
  GET  /                                       -> serves the browser demo

Run:  uvicorn app.api:app --reload --port 8000
      then open http://localhost:8000
"""
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .model import get_analyzer

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")

app = FastAPI(
    title="Bharat-Scam-X",
    description="Attack-signature scam detection for Indian language messaging.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MAX_LEN = 2000
MAX_BATCH = 500


class AnalyzeIn(BaseModel):
    text: str = Field(..., description="The message to analyse")


class BatchIn(BaseModel):
    texts: List[str] = Field(..., description="Messages to analyse")


@app.get("/health")
def health():
    a = get_analyzer()
    return {
        "status": "ok",
        "signature_features": len(a.vec_sig.vocabulary_),
        "binary_features": len(a.vec_bin.vocabulary_),
        "fields": list(a.heads.keys()),
        "note": "Signature heads trained on 1,823 synthetic messages across nine "
                "language varieties. Binary detector additionally trained on 24,000 "
                "real English messages and has no competence on Indic scripts.",
    }


@app.post("/analyze")
def analyze(body: AnalyzeIn):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "text is empty")
    if len(text) > MAX_LEN:
        raise HTTPException(413, f"text longer than {MAX_LEN} characters")
    return get_analyzer().analyze(text)


@app.post("/batch")
def batch(body: BatchIn):
    if not body.texts:
        raise HTTPException(400, "texts is empty")
    if len(body.texts) > MAX_BATCH:
        raise HTTPException(413, f"more than {MAX_BATCH} messages")
    a = get_analyzer()
    out = []
    for t in body.texts:
        t = (t or "").strip()[:MAX_LEN]
        out.append(a.analyze(t) if t else {"error": "empty message"})
    return {"count": len(out), "results": out}


if os.path.isdir(WEB):
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
