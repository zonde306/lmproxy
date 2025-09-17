#!/bin/bash
cd src
python3 -m uvicorn main:app --port 13579
