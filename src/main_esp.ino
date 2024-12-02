#include <esp_now.h>
#include <WiFi.h>

// Example structure for received data
typedef struct {
  char message[32];
} StatusMessage;

StatusMessage receivedMessage;

void onDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
  memcpy(&receivedMessage, incomingData, sizeof(receivedMessage));
  Serial.println(receivedMessage.message); // Forward to Raspberry Pi
}

void setup() {
  Serial.begin(115200); // Serial communication with Raspberry Pi

  // Initialize Wi-Fi in station mode
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register the receive callback
  esp_now_register_recv_cb(onDataRecv);
}

void loop() {
  // Nothing to do here; all data handling happens in the callback
}
