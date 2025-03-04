# ESP32 Circuit Wiring Guide

This document explains how to wire up the ESP32 with a **DC-DC buck converter, optocoupler signals, LEDs, and input components**.

## **1. Power Supply & ESP32 Connections**
| Component | Pin Name | Connected To | Notes |
|-----------|---------|--------------|-------|
| **24V Input** | VIN | MP2315 VIN | Main power source |
| **MP2315 (Buck Converter)** | VOUT | ESP32 **5V Pin** | Provides stable 5V power |
| **MP2315** | GND | Common GND | Ground connection for all components |
| **ESP32** | 3.3V | Various Components | Powers optocouplers, LEDs, and GPIO pull-ups |
| **ESP32** | GND | Common GND | Ground for all components |

---

## **2. Optocoupler (TLP291-4) to ESP32 & External Inputs**
| TLP291-4 Pin | Connected To | ESP32 GPIO | Notes |
|--------------|-------------|------------|-------|
| **Pin 1 (Anode 1)** | External Signal 1 (Ramp Up) | - | Uses **220Ω series resistor** |
| **Pin 2 (Cathode 1)** | GND | - | Completes LED circuit |
| **Pin 3 (Anode 2)** | External Signal 2 (Ramp Down) | - | Uses **220Ω series resistor** |
| **Pin 4 (Cathode 2)** | GND | - | Completes LED circuit |
| **Pin 5 (Anode 3)** | External Signal 3 (Home) | - | Uses **220Ω series resistor** |
| **Pin 6 (Cathode 3)** | GND | - | Completes LED circuit |
| **Pin 9 (Emitter 1)** | GND | - | Shared ground |
| **Pin 10 (Collector 1)** | ESP32 GPIO14 | **Ramp Up Status** |
| **Pin 11 (Emitter 2)** | GND | - | Shared ground |
| **Pin 12 (Collector 2)** | ESP32 GPIO27 | **Ramp Down Status** |
| **Pin 13 (Emitter 3)** | GND | - | Shared ground |
| **Pin 14 (Collector 3)** | ESP32 GPIO26 | **Home Status** |
| **ESP32 GPIOs** | **10kΩ Pull-down Resistor** | **GND** | Ensures stable LOW state |

---

## **3. Status LEDs for Optocoupler Outputs**
| LED Color | LED Anode (+) | LED Cathode (-) | Resistor | Notes |
|-----------|--------------|----------------|---------|------|
| **Red (Ramp Up)** | 3.3V | ESP32 GPIO14 | 470Ω | Turns ON when Ramp Up is active |
| **Green (Ramp Down)** | 3.3V | ESP32 GPIO27 | 470Ω | Turns ON when Ramp Down is active |
| **Blue (Home)** | 3.3V | ESP32 GPIO26 | 470Ω | Turns ON when Home is active |

---

## **4. Capacitors for Power Stability**
| Capacitor | Connected To | Purpose |
|-----------|-------------|---------|
| **22µF 25V** | MP2315 VIN (24V) to GND | Stabilizes DC-DC input |
| **10µF 25V** | MP2315 VOUT (5V) to GND | Stabilizes ESP32 power |
| **0.1µF 10V x2** | ESP32 3.3V rail to GND | Reduces high-frequency noise |

---

## **Final Notes**
- **Ensure correct polarity** for power input components.
- **Mount capacitors close to the MP2315 regulator** for best stability.
- **Use 10kΩ pull-downs for stable ESP32 GPIO readings.**