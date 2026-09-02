---
uuid: paper-yolo-realtime
title: "YOLO: real-time object detection with a single neural network"
summary: "Single CNN predicts bounding boxes and class probabilities for all objects in one forward pass; 45 FPS on Titan X; trades small accuracy for big speed."
status: active
tags: [yolo, detection, real-time]
source: "https://arxiv.org/abs/1506.02640"
---
## Answer
YOLO (You Only Look Once) reframes detection as a single regression problem: one CNN predicts bounding boxes and class probabilities in one forward pass.

Speed: 45 FPS on a Titan X GPU.
Accuracy: lower than Faster R-CNN but acceptable for many use cases.

## Don't
Don't apply YOLO to small-object detection without considering YOLOv3+ variants -- the original struggles with small objects.
