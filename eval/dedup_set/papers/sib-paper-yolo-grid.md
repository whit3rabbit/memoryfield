---
uuid: sib-paper-yolo-grid
title: YOLO's per-cell class prediction makes it weak on small objects that cluster together
summary: Because each grid cell predicts only one set of class probabilities shared across its boxes, YOLO struggles when multiple small objects (like a flock of birds) have centers in the same cell, a limitation two-stage detectors with per-proposal classification don't share.
---
## Answer
The grid design that makes YOLO fast also creates a specific failure mode the base architecture doesn't fully solve. Each grid cell outputs one shared set of class probabilities regardless of how many bounding boxes it predicts, so if two or more small objects have their centers fall in the same cell, the model can only assign one class label to that cell's predictions. In practice this shows up most on scenes with many small, closely packed objects, a flock of birds, a crowd, a cluster of small products on a shelf.

Two-stage detectors that generate per-region proposals first and classify each proposal independently don't have this constraint, since each proposal gets its own classification pass rather than sharing one label across everything centered in a coarse spatial cell. This spatial-constraint tradeoff, not detection speed or the confidence formula, is the specific limitation later YOLO revisions targeted with finer grids and anchor boxes.
