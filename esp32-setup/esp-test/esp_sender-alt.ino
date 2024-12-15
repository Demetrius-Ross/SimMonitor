#include <esp_now.h>
#include <WiFi.h>
#include <Update.h>

// Receiver ESP MAC Address (replace with your main ESP's MAC address)
uint8_t receiverMAC[] = {0x78, 0xE3, 0x6D, 0xDF, 0x69, 0x7C};

// Unique label for this Node
#define SELF_LABEL "PC-12"

// Data structure to send normal data
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: In Motion, 1: Ramp Up, 2: Ramp Down
  int motionState;  // 1: Sim Down (Home), 2: Sim Up
  int status;       // 1: Connected, 0: No Data
} Message;

// Data structure for OTA command
typedef struct {
  char targetLabel[10];  // Label of the target ESP32
  uint8_t firmwareChunk[1024]; // Firmware data chunk
  size_t chunkSize;      // Size of the firmware chunk
  bool otaStart;         // Flag to indicate start of OTA
} OTACommand;

Message myData;
Message previousData; // To store the previous state for change detection

bool otaMode = false; // Flag to indicate OTA mode
unsigned long otaStartTime = 0; // Track OTA start time
const unsigned long otaTimeout = 30000; // 30-second timeout for OTA mode

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
    Serial.println("Failed to add peer");
    return;
  }

  // Initialize previous data with default values
  strcpy(previousData.simName, "");
  previousData.rampState = -1; // Invalid initial state
  previousData.motionState = -1;
  previousData.status = -1;

  Serial.println("Sender ESP ready to send messages.");
}

void loop() {
  if (otaMode) {
    // Exit OTA mode if timeout occurs
    if (millis() - otaStartTime > otaTimeout) {
      otaMode = false;
      Serial.println("OTA mode timed out, resuming normal operation.");
    }
    return; // Skip the normal operation loop while in OTA mode
  }

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

  // Check if the current state is different from the previous state
  if (myData.rampState != previousData.rampState ||
      myData.motionState != previousData.motionState ||
      myData.status != previousData.status) {

    // Send data via ESP-NOW
    esp_err_t result = esp_now_send(receiverMAC, (uint8_t *)&myData, sizeof(myData));
    if (result == ESP_OK) {
      Serial.printf("Data sent: RampState=%d, MotionState=%d, Status=%d\n",
                    myData.rampState, myData.motionState, myData.status);
    } else {
      Serial.println("Error sending data.");
    }

    // Update the previous state
    previousData = myData;
  }

  delay(50); // Small delay to prevent rapid loops
}
