#include <esp_now.h>
#include <WiFi.h>

// Data structure to receive
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: Down, 1: Up
  int motionState;  // 0: Down, 1: Up
  int status;       // 0: No Data, 1: Connected
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

  // Log the received data
  Serial.println("Received Data:");
  Serial.print("Simulator Name: ");
  Serial.println(receivedData->simName);

  Serial.print("Ramp State: ");
  Serial.println(receivedData->rampState == 1 ? "Up" : "Down");

  Serial.print("Motion State: ");
  Serial.println(receivedData->motionState == 1 ? "Up" : "Down");

  Serial.print("Status: ");
  Serial.println(receivedData->status == 1 ? "Connected" : "No Data");

  // Forward the data to the Raspberry Pi via Serial
  Serial.print(receivedData->simName);
  Serial.print(",");
  Serial.print(receivedData->rampState);
  Serial.print(",");
  Serial.print(receivedData->motionState);
  Serial.print(",");
  Serial.println(receivedData->status);
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
