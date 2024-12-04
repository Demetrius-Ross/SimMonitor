#include <esp_now.h>
#include <WiFi.h>

// Receiver ESP MAC Address
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C}; // Main ESP MAC address

// Data structure to send
typedef struct {
  char simName[10];    // Name of the simulator
  int rampState;       // 0: in motion, 1: ramp up, 2: ramp down
  int motionState;     // 1: sim down (home), 2: sim up
  int status;          // 1: Connected, 0: No Data
} Message;

Message myData;

// Pin definitions for LEDs
#define RAMP_UP_PIN 14
#define RAMP_DOWN_PIN 27
#define SIM_HOME_PIN 26

void onSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last Packet Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);

  // Initialize GPIO pins
  pinMode(RAMP_UP_PIN, INPUT);
  pinMode(RAMP_DOWN_PIN, INPUT);
  pinMode(SIM_HOME_PIN, INPUT);

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
  // Determine the ramp state
  int rampUp = digitalRead(RAMP_UP_PIN);
  int rampDown = digitalRead(RAMP_DOWN_PIN);

  if (rampUp == HIGH && rampDown == LOW) {
    myData.rampState = 1; // Ramp is up
  } else if (rampUp == LOW && rampDown == HIGH) {
    myData.rampState = 2; // Ramp is down
  } else {
    myData.rampState = 0; // Ramp is in motion
  }

  // Determine the motion state
  int simHome = digitalRead(SIM_HOME_PIN);
  myData.motionState = (simHome == HIGH) ? 1 : 2; // 1: Sim is down, 2: Sim is up

  // Update the connection status
  myData.status = 1; // Always set to connected if the data is being sent

  // Log the data to be sent
  Serial.print("Sending Data: ");
  Serial.print(myData.simName);
  Serial.print(", Ramp State: ");
  Serial.print(myData.rampState);
  Serial.print(", Motion State: ");
  Serial.print(myData.motionState);
  Serial.print(", Status: ");
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
