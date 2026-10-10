# 8. Final report outline and viva preparation

## Report chapters (suggested; follow your university template)

1. **Introduction:** motivation, problem statement, objectives, scope, organisation of the report
2. **Literature survey:** conventional detectors (smoke/heat/flame IR), vision-based detection (colour models →
   CNN classifiers → YOLO family), sensor fusion. Compare 8–10 papers in a table (method, dataset, accuracy, limitation).
3. **System requirements:** hardware/software requirements, functional and non-functional requirements
4. **System design:** architecture diagram, data flow, fusion rules, circuit diagram, database schema, API, UI wireframes
5. **Implementation**
   * 5.1 Dataset and YOLOv8 training (Tanishka)
   * 5.2 Web dashboard (Tanishk)
   * 5.3 Hardware and Raspberry Pi (Tanmay)
   * 5.4 Desktop GUI (Shubham)
6. **Testing and results:** metrics table, confusion matrix, PR curve, live tests, false-alarm rate, latency, Pi FPS
7. **Conclusion and future scope:** thermal camera, LoRa/GSM alerts, automatic suppression, cloud fleet dashboard
8. **References** (IEEE style, including the dataset and Ultralytics citations)
9. **Appendix:** code listing highlights, BOM, user manual, photos

## Likely viva questions

**Model**
* Why YOLOv8 and not a classifier? → It gives the *location* of the fire, runs in real time and handles several fires per image.
* What is mAP@50? IoU? Precision vs recall? Which matters more for fire? → Recall: a missed fire is worse than a false alarm.
* Why YOLOv8n? → Speed on the Raspberry Pi. Show the n vs s comparison table.
* How did you avoid false positives? → Hard negatives in the dataset, N-consecutive-frame rule, sensor fusion.
* How did you split the data, and is there leakage? → 70/20/10 after deduplication, test never used for tuning.

**Hardware**
* Why do you need an ADC? Why the voltage divider? Why a transistor for the buzzer? (see [05](05_hardware.md#why-each-part-is-there-likely-viva-questions))
* What does the MQ-2 actually measure? → Resistance change of SnO₂ with combustible gas/smoke. It is relative, so it needs calibration.
* DHT22 accuracy? → ±0.5 °C, 0.5 Hz maximum read rate.

**Software**
* How does the device talk to the dashboard? → HTTP POST JSON with an API key. The browser polls REST endpoints.
* What happens if Wi-Fi fails? → Detection and the local buzzer keep working. Network errors are logged and ignored.
* How do you keep the GUI responsive? → Worker thread + queue, with Tk updates only on the main thread.
