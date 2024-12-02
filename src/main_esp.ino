#include <esp_now.h>
#include <WiFi.h>

// Data structure to receive
typedef struct {
  char message[32];
} Message;

Message incomingData;

// Callback function for ESP-NOW
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  memcpy(&incomingData, incomingData, len);

  // Forward the received message and MAC address to the Raspberry Pi via Serial
  Serial.print("Sender MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.print(recv_info->src_addr[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.print("\nMessage: ");
  Serial.println((char *)incomingData);
}

void setup() {
  Serial.begin(115200); // Open serial communication with Raspberry Pi

  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register the receive callback
  esp_now_register_recv_cb(onDataRecv);

  Serial.println("Main ESP ready to forward messages.");
}

void loop() {
  // Main ESP continuously forwards messages to the Raspberry Pi
}
