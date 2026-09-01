---
uuid: para-paper-yolo-grid
title: YOLO splits the image into a grid and lets each cell own the objects centered in it
summary: The image is divided into an SxS grid (S=7 default), each cell predicts B=2 candidate boxes plus a confidence equal to P(object) times IoU, and a cell is only responsible for an object whose center point falls inside it.
---
## Answer
YOLO frames detection as a single grid-based regression rather than a two-stage propose-then-classify pipeline. The input image is partitioned into an SxS grid, S=7 by default, and each cell is assigned ownership of any object whose center point lands within its boundaries, regardless of how much of the object's area spills into neighboring cells.

Each cell predicts B bounding boxes (B=2 by default), and each box carries five numbers: x, y, w, h, and a confidence score defined as P(object present) multiplied by the predicted IoU with the ground truth. Separately, each cell predicts one set of class probabilities, conditioned on an object being present, shared across that cell's boxes. Stacking all of this together gives an output tensor of shape S x S x (B*5 + C), where C is the number of object classes.
