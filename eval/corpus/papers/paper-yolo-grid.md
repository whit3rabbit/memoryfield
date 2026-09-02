---
uuid: paper-yolo-grid
title: "YOLO: divides image into SxS grid; each cell predicts B boxes"
summary: "Grid-based prediction: each cell is responsible for objects whose center falls in that cell; B=2 default; confidence score is P(object) times IoU."
status: active
tags: [yolo, architecture]
source: "https://arxiv.org/abs/1506.02640"
---
## Answer
YOLO architecture:
1. Divide the image into an SxS grid (default S=7).
2. Each grid cell predicts B bounding boxes (default B=2).
3. Each box has: (x, y, w, h, confidence).
4. Each cell also predicts class probabilities (conditioned on object presence).

Total output tensor: S x S x (B * 5 + C) where C is the number of classes.
