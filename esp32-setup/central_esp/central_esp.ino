#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
// Data structure to receive
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: In motion, 1: Ramp Up, 2: Ramp Down
  int motionState;  // 1: Sim Down (Home), 2: Sim Up
  int status;       // 0: No Data, 1: Connected
} Message;

uint8_t newMACAddress[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C};

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
  esp_err_t result = esp_wifi_set_mac(WIFI_IF_STA, &newMACAddress[0]);
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  Serial.println(WiFi.macAddress());
  // Register the receive callback
  esp_now_register_recv_cb(onDataRecv);

  Serial.println("Main ESP ready to forward messages.");
}

void loop() {
  // Nothing to do in the main loop; data is handled in the callback
}
