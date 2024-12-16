#include <esp_now.h>
#include <WiFi.h>
#include <Update.h>

// Data structure to receive normal simulator data
typedef struct {
  char simName[10]; // Simulator name
  int rampState;    // 0: In motion, 1: Ramp Up, 2: Ramp Down
  int motionState;  // 1: Sim Down (Home), 2: Sim Up
  int status;       // 0: No Data, 1: Connected
} Message;

// Data structure for OTA commands
typedef struct {
  char targetLabel[10];    // Target Node ESP32 label
  uint8_t firmwareChunk[1024]; // Firmware data chunk
  size_t chunkSize;        // Size of the firmware chunk
  bool otaStart;           // Flag to indicate the start of OTA
} OTACommand;

Message incomingData; // Normal simulator data
OTACommand otaCommand; // For OTA commands

bool otaMode = false;             // Flag to indicate OTA mode
unsigned long otaStartTime = 0;   // Track OTA start time
const unsigned long otaTimeout = 30000; // 30-second timeout for OTA mode

// Callback function for ESP-NOW
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  if (otaMode) {
    // Ignore all incoming ESP-NOW data while in OTA mode
    return;
  }

  // Check if incoming data is normal simulator data
  if (len == sizeof(Message)) {
    const Message *receivedData = (const Message *)incomingData;

    // Forward the data to the Raspberry Pi via Serial
    Serial.print(receivedData->simName);
    Serial.print(",");
    Serial.print(receivedData->rampState);
    Serial.print(",");
    Serial.print(receivedData->motionState);
    Serial.print(",");
    Serial.println(receivedData->status);

  } else if (len >= sizeof(OTACommand)) {
    // Incoming OTA command
    const OTACommand *receivedCmd = (const OTACommand *)incomingData;

    // Forward the OTA command as a broadcast
    esp_err_t result = esp_now_send(NULL, (uint8_t *)receivedCmd, sizeof(OTACommand));
    if (result == ESP_OK) {
      Serial.printf("Broadcasted OTA command for target: %s\n", receivedCmd->targetLabel);
    } else {
      Serial.println("Failed to broadcast OTA command.");
    }
  } else {
    Serial.println("Unknown data received!");
  }
}

// Function to handle OTA updates
void handleOTA() {
  if (Serial.available() > 0) {
    // Reset timeout timer
    otaStartTime = millis();

    // Read incoming firmware data from Serial
    uint8_t otaBuffer[1024];
    size_t len = Serial.readBytes(otaBuffer, sizeof(otaBuffer));

    // Write firmware data to flash
    if (!Update.isRunning()) {
      Update.begin(UPDATE_SIZE_UNKNOWN); // Start OTA update
    }

    Update.write(otaBuffer, len);

    // Finalize update if all chunks are received
    if (Update.end()) {
      Serial.println("OTA update completed successfully!");
      ESP.restart(); // Restart after a successful update
    } else if (Update.hasError()) {
      Serial.printf("OTA error: %s\n", Update.errorString());
    }
  }

  // Check for timeout
  if (millis() - otaStartTime > otaTimeout) {
    otaMode = false; // Exit OTA mode after timeout
    Serial.println("Exiting OTA mode due to timeout.");
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
  if (otaMode) {
    handleOTA(); // Handle OTA updates when in OTA mode
    return;
  }

  // Check for OTA activation command
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');

    if (command.startsWith("OTA:")) {
      // Parse the target label from the command
      String targetLabel = command.substring(4); // Extract substring from index 4
      targetLabel.trim();                        // Trim whitespace in-place

      strncpy(otaCommand.targetLabel, targetLabel.c_str(), sizeof(otaCommand.targetLabel));
      otaCommand.otaStart = true; // Indicate OTA start
      otaCommand.chunkSize = 0;   // No firmware data yet

      // Broadcast the OTA start command
      esp_err_t result = esp_now_send(NULL, (uint8_t *)&otaCommand, sizeof(OTACommand));
      if (result == ESP_OK) {
        Serial.printf("Broadcasted OTA start command for target: %s\n", otaCommand.targetLabel);
      } else {
        Serial.println("Failed to broadcast OTA start command.");
      }
    }
  }
}
