#include <esp_now.h>
#include <WiFi.h>

// Data structure to receive
typedef struct {
  int ledStatus[4]; // Store the status of the 4 LEDs
} Message;

Message incomingData;

// Callback function for ESP-NOW
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  // Validate the data length
  if (len != sizeof(Message)) {
    Serial.println("Error: Invalid data size received!");
    return;
  }

  // Cast the incoming data to our structure
  const Message *receivedData = (const Message *)incomingData;

  // Log the received LED statuses
  Serial.print("Received LED Statuses: ");
  for (int i = 0; i < 4; i++) {
    Serial.print(receivedData->ledStatus[i]);
    Serial.print(" ");
  }
  Serial.println();

  // Forward the data to the Raspberry Pi
  for (int i = 0; i < 4; i++) {
    Serial.print("LED");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(receivedData->ledStatus[i]);
  }
}

void setup() {
  Serial.begin(115200); // Open serial communication with Raspberry Pi

  // Initialize Wi-Fi in station mode
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
  // Nothing to do in the main loop; data is handled in the callback
}
