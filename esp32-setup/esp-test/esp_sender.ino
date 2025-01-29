#include <esp_now.h>
#include <WiFi.h>

// Receiver ESP MAC Address (replace with your main ESP's MAC address)
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C};

// Unique label for this Node
#define SELF_LABEL "PC-12"

// Data structure to hold simulator state
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: In Motion, 1: Ramp Up, 2: Ramp Down
  int motionState;  // 1: Sim Down (Home), 2: Sim Up
  int status;       // 1: Connected, 0: No Data
} Message;

Message myData;
Message previousData; // To store the previous state for change detection

// Pin definitions
#define RAMP_UP_PIN 14     // Ramp Up
#define RAMP_DOWN_PIN 27   // Ramp Down
#define SIM_HOME_PIN 26    // Sim at Home

void onSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Message Sent. Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Failure");
}

void setup() {
  Serial.begin(115200);

  // Initialize GPIO pins
  pinMode(RAMP_UP_PIN, INPUT);
  pinMode(RAMP_DOWN_PIN, INPUT);
  pinMode(SIM_HOME_PIN, INPUT);

  // Set simulator name
  strcpy(myData.simName, SELF_LABEL);

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
    Serial.println("Failed to add peer, retrying...");
    delay(1000);
    esp_now_add_peer(&peerInfo);
  }

  // Initialize previous data
  previousData.rampState = -1;
  previousData.motionState = -1;
  previousData.status = -1;

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
  } else if (rampUp == LOW) {
    myData.rampState = 1; // Ramp Up
  } else if (rampDown == LOW) {
    myData.rampState = 2; // Ramp Down
  } else {
    myData.rampState = 0; // Default to "In Motion" if no valid state is detected
  }

  // Determine motion state
  myData.motionState = (simHome == LOW) ? 1 : 2; // 1: Sim Down (Home), 2: Sim Up

  // Determine status
  myData.status = (rampUp || rampDown || simHome) ? 1 : 0; // 1: Connected, 0: No Data

  // Check for state changes
  if (memcmp(&myData, &previousData, sizeof(myData)) != 0) {
    // Construct the message with delimiters
    String message = String("<") + myData.simName + "," + 
                     String(myData.rampState) + "," + 
                     String(myData.motionState) + "," + 
                     String(myData.status) + String(">");

    // Send the message as a byte array
    esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)message.c_str(), message.length());

    // Log the sent message
    if (result == ESP_OK) {
        Serial.printf("Data sent: %s\n", message.c_str());
    } else {
        Serial.println("Error sending data, retrying...");
        esp_now_send(receiverMAC, (uint8_t *)message.c_str(), message.length()); // Retry
    }

    // Update previous data
    memcpy(&previousData, &myData, sizeof(myData));
  }

  delay(50); // Small delay to debounce and avoid rapid loops
}
