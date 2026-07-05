# YOLO Multimodal Search Safe Claims

## Supported Claims

- S100P can run local YOLO object detection through the board-side TROS `dnn_node_example` route.
- Multimodal Search v2 adds an object-label index for images and sampled video keyframes.
- The API can search by supported English or Chinese object aliases such as person, car, bus, laptop, book, keyboard, mouse, tv, stop sign, and kite when those objects were detected in the local index.
- Results return redacted asset IDs, object labels, confidence, normalized bounding boxes, timestamps for video keyframes, and evidence refs.
- The route is local-only and does not use cloud vision.

## Claims To Avoid

- Do not claim full image or video understanding.
- Do not claim face identity, sensitive attribute recognition, camera monitoring, or employee monitoring.
- Do not claim every COCO label is verified on the production fixture.
- Do not claim YOLO replaces FTS, RAG, or image embeddings. It is an additional local visual-object signal.
- Do not claim PC deployment when the PC is only used for SSH, browser, or recording.
