#include <esp_now.h>
#include <WiFi.h>

// Receiver ESP MAC Address (replace with your main ESP's MAC address)
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C};

// Data structure to send
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: In Motion, 1: Ramp Up, 2: Ramp Down
  int motionState;  // 1: Sim Down (Home), 2: Sim Up
  int status;       // 1: Connected, 0: No Data
} Message;

Message myData;

// Pin definitions for LEDs
#define RAMP_UP_PIN 14     // Ramp Up
#define RAMP_DOWN_PIN 27   // Ramp Down
#define SIM_HOME_PIN 26    // Sim at Home

void onSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Send callback, no extra logging to keep things clean
}

void setup() {
  Serial.begin(115200);

  // Initialize GPIO pins
  pinMode(RAMP_UP_PIN, INPUT);
  pinMode(RAMP_DOWN_PIN, INPUT);
  pinMode(SIM_HOME_PIN, INPUT);

  // Set simulator name
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
  // Read states from the input pins
  int rampUp = digitalRead(RAMP_UP_PIN);
  int rampDown = digitalRead(RAMP_DOWN_PIN);
  int simHome = digitalRead(SIM_HOME_PIN);

  // Determine ramp state
  if (rampUp == HIGH && rampDown == HIGH) {
    myData.rampState = 0; // In Motion
  } else if (rampUp == HIGH) {
    myData.rampState = 1; // Ramp Up
  } else if (rampDown == HIGH) {
    myData.rampState = 2; // Ramp Down
  } else {
    myData.rampState = 0; // Default to "In Motion" if no valid state is detected
  }

  // Determine motion state
  myData.motionState = (simHome == HIGH) ? 1 : 2; // 1: Sim Down (Home), 2: Sim Up

  // Determine status
  myData.status = (rampUp || rampDown || simHome) ? 1 : 0; // 1: Connected, 0: No Data

  // Send data via ESP-NOW
  esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)&myData, sizeof(myData));

  delay(2000); // Send data every 2 seconds
}