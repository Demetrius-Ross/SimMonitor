from machine import Pin, I2C, ADC
import time

# --------------------------------------
# LM35 Temperature Sensor
# --------------------------------------
adc = ADC(Pin(34))
adc.atten(ADC.ATTN_11DB)   # 0–3.3V


while True:
    print(adc.read())
    time.sleep(0.2)

