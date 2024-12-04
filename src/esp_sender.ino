#include <esp_now.h>
#include <WiFi.h>

// Receiver ESP MAC Address
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C}; // Main ESP MAC address

// Data structure to send
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: Down, 1: Up
  int motionState;  // 0: Down, 1: Up
  int status;       // 0: No Data, 1: Connected
} Message;

Message myData;

// Pin definitions for LEDs
#define RAMP_UP_PIN 14
#define RAMP_DOWN_PIN 27
#define SIM_UP_PIN 26
#define SIM_DOWN_PIN 25

void onSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last Packet Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);

  // Initialize GPIO pins
  pinMode(RAMP_UP_PIN, INPUT);
  pinMode(RAMP_DOWN_PIN, INPUT);
  pinMode(SIM_UP_PIN, INPUT);
  pinMode(SIM_DOWN_PIN, INPUT);

  // Set the simulator name
  strcpy(myData.simName, "PC-12");

  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register send callback
  esp_now_register_send_cb(onSent);

  // Register peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, receiverMAC, 6);
  peerInfo.channel = 0; // Default channel
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("Sender ESP ready to send messages.");
}

void loop() {
  // Determine the ramp and motion states
  int rampUp = digitalRead(RAMP_UP_PIN);
  int rampDown = digitalRead(RAMP_DOWN_PIN);
  int simUp = digitalRead(SIM_UP_PIN);
  int simDown = digitalRead(SIM_DOWN_PIN);

  // Assign states based on input
  myData.rampState = (rampUp == HIGH) ? 1 : 0;       // Ramp Up: 1, Ramp Down: 0
  myData.motionState = (simUp == HIGH) ? 1 : 0;     // Sim Up: 1, Sim Down: 0
  myData.status = (rampUp || rampDown || simUp || simDown) ? 1 : 0; // Connected if any LED is HIGH

  // Log the data to be sent
  Serial.print("Sending Data: ");
  Serial.print(myData.simName);
  Serial.print(", ");
  Serial.print(myData.rampState);
  Serial.print(", ");
  Serial.print(myData.motionState);
  Serial.print(", ");
  Serial.println(myData.status);

  // Send the data
  esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)&myData, sizeof(myData));

  if (result == ESP_OK) {
    Serial.println("Message sent successfully");
  } else {
    Serial.println("Failed to send message");
  }

  delay(2000); // Send data every 2 seconds
}
