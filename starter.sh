#!/usr/bin/bash
source /home/rose/.envs/mininet-venv/bin/activate
pip install -r requirements.txt
python3 main.py --topo tree --size 3
