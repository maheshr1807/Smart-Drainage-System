
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ---------------- WIFI: WOKWI ----------------
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// ---------------- PUBLIC MQTT BROKER ----------------
const char* MQTT_SERVER = "broker.hivemq.com";
const uint16_t MQTT_PORT = 1883;
const char* MQTT_TOPIC = "smartsewer/sensors";

WiFiClient mqttNetworkClient;
PubSubClient mqttClient(mqttNetworkClient);

// ---------------- PIN CONFIGURATION ----------------
// Zone 1 HC-SR04
const int TRIG1 = 5;
const int ECHO1 = 18;

// Zone 2 HC-SR04
const int TRIG2 = 16;
const int ECHO2 = 17;

// Zone 3 HC-SR04
const int TRIG3 = 19;
const int ECHO3 = 23;

// Other sensors and outputs
const int FLOW_SENSOR_PIN = 34;
const int RAIN_SENSOR_PIN = 35;
const int MQ2_AO_PIN = 32;
const int LED_PIN = 25;
const int BUZZER_PIN = 26;

// ---------------- LCD ----------------
LiquidCrystal_I2C lcd(0x27, 20, 4);

// ---------------- SETTINGS ----------------
const float SEWER_DEPTH_CM = 100.0;

// MQ-2 ADC threshold for a demo gas warning.
// This is not a calibrated ppm threshold.
const int GAS_ADC_THRESHOLD = 1000;

const unsigned long SENSOR_INTERVAL_MS = 2000;
const unsigned long MQTT_RETRY_MS = 5000;

unsigned long lastSensorRead = 0;
unsigned long lastMqttAttempt = 0;

// ---------------- SENSOR VALUES ----------------
float zone1 = 0;
float zone2 = 0;
float zone3 = 0;

float flowRate = 0;
float rainIntensity = 0;
int gasValue = 0;

int blockageRisk = 0;
int overflowRisk = 0;

const bool DEMO_TARGET_OUTPUT = false;

String suspectedArea = "UNKNOWN";
String gasStatus = "GAS SAFE";
String workerSafety = "SAFE TO ENTER";
String overallStatus = "NORMAL";

// ---------------- HC-SR04 ----------------
float readDistanceCM(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(3);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);

  // Timeout means no valid echo.
  if (duration == 0) {
    return -1.0;
  }

  return duration * 0.0343f / 2.0f;
}

float readWaterLevel(int trigPin, int echoPin) {
  float distance = readDistanceCM(trigPin, echoPin);

  if (distance < 0) {
    return -1.0;
  }

  float level = 100.0f -
                (distance / SEWER_DEPTH_CM * 100.0f);

  return constrain(level, 0.0f, 100.0f);
}

// ---------------- OTHER SENSORS ----------------
float readFlowRate() {
  int raw = analogRead(FLOW_SENSOR_PIN);

  // Demo calibration: ADC 0..4095 -> 0..10 L/min.
  // Adjust this mapping to match your virtual sensor model.
  return (raw / 4095.0f) * 10.0f;
}

float readRainIntensity() {
  int raw = analogRead(RAIN_SENSOR_PIN);

  // Demo scale: 0..4095 -> 0..100.
  // Reverse the mapping if your rain sensor model behaves
  // in the opposite direction.
  return (raw / 4095.0f) * 100.0f;
}

int readGasValue() {
  return analogRead(MQ2_AO_PIN);
}

// ---------------- RISK CALCULATION ----------------
void calculateRisks() {
  if (DEMO_TARGET_OUTPUT) {
    // Fixed demonstration values for the requested presentation.
    zone1 = 53.4;
    zone2 = 71.6;
    zone3 = 57.5;

    flowRate = 1.65;
    rainIntensity = 13.2;
    gasValue = 1693;

    blockageRisk = 55;
    suspectedArea = "BETWEEN Z2-Z3";
    overflowRisk = 45;

    gasStatus = "GAS DETECTED";
    workerSafety = "DO NOT ENTER";
    overallStatus = "CRITICAL - GAS HAZARD";
    return;
  }

  // Live-sensor mode: use the actual sensor readings.
  bool gasDetected = gasValue >= GAS_ADC_THRESHOLD;

  gasStatus = gasDetected ? "GAS DETECTED" : "GAS SAFE";
  workerSafety = gasDetected ? "DO NOT ENTER" : "SAFE TO ENTER";

  float maxLevel = 0.0;
  if (zone1 >= 0) maxLevel = max(maxLevel, zone1);
  if (zone2 >= 0) maxLevel = max(maxLevel, zone2);
  if (zone3 >= 0) maxLevel = max(maxLevel, zone3);

  float zoneDifference = 0.0;
  if (zone2 >= 0 && zone3 >= 0) {
    zoneDifference = abs(zone2 - zone3);
  }

  blockageRisk = constrain(
      (int)round(35.0 + zoneDifference * 1.4),
      0, 100
  );

  overflowRisk = constrain(
      (int)round(maxLevel * 0.63),
      0, 100
  );

  if (zone2 >= 0 && zone3 >= 0 && zone2 >= zone3) {
    suspectedArea = "BETWEEN Z2-Z3";
  } else if (zone1 >= 0 && zone2 >= 0 && zone1 >= zone2) {
    suspectedArea = "BETWEEN Z1-Z2";
  } else {
    suspectedArea = "CHECK ALL ZONES";
  }

  if (gasDetected) {
    overallStatus = "CRITICAL - GAS HAZARD";
  } else if (maxLevel >= 90.0) {
    overallStatus = "CRITICAL - OVERFLOW";
  } else if (maxLevel >= 70.0 || blockageRisk >= 60) {
    overallStatus = "WARNING";
  } else {
    overallStatus = "NORMAL";
  }
}

// ---------------- SERIAL REPORT ----------------
void printReport() {
  Serial.println();
  Serial.println("SMART SEWER MONITORING");
  Serial.println("3 Zone Monitoring Active");
  Serial.println();

  if (zone1 >= 0) {
    Serial.printf("Zone 1 Water Level: %.1f %%\n", zone1);
  } else {
    Serial.println("Zone 1 Water Level: SENSOR ERROR");
  }

  if (zone2 >= 0) {
    Serial.printf("Zone 2 Water Level: %.1f %%\n", zone2);
  } else {
    Serial.println("Zone 2 Water Level: SENSOR ERROR");
  }

  if (zone3 >= 0) {
    Serial.printf("Zone 3 Water Level: %.1f %%\n", zone3);
  } else {
    Serial.println("Zone 3 Water Level: SENSOR ERROR");
  }

  Serial.println();
  Serial.printf("Flow Rate: %.2f L/min\n", flowRate);
  Serial.printf("Rain Intensity: %.1f\n", rainIntensity);
  Serial.printf("Gas Value: %d\n", gasValue);
  Serial.printf("Gas Status: %s\n", gasStatus.c_str());
  Serial.printf("Worker Safety: %s\n", workerSafety.c_str());
  Serial.println();
  Serial.printf("Blockage Risk: %d %%\n", blockageRisk);
  Serial.printf("Suspected Area: %s\n", suspectedArea.c_str());
  Serial.printf("Overflow Risk: %d %%\n", overflowRisk);
  Serial.printf("Overall Status: %s\n", overallStatus.c_str());
  Serial.println("----------------------------------------");
}

// ---------------- LCD DISPLAY ----------------
void updateLCD() {
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("SMART SEWER SYSTEM");

  lcd.setCursor(0, 1);
  lcd.print("Z1:");
  if (zone1 >= 0) lcd.print(zone1, 1);
  else lcd.print("--");
  lcd.print("% Z2:");
  if (zone2 >= 0) lcd.print(zone2, 1);
  else lcd.print("--");
  lcd.print("%");

  lcd.setCursor(0, 2);
  lcd.print("Z3:");
  if (zone3 >= 0) lcd.print(zone3, 1);
  else lcd.print("--");
  lcd.print("% Gas:");
  lcd.print(gasValue);

  lcd.setCursor(0, 3);
  if (gasValue >= GAS_ADC_THRESHOLD) {
    lcd.print("GAS! DO NOT ENTER");
  } else if (overflowRisk >= 55) {
    lcd.print("OVERFLOW WARNING");
  } else {
    lcd.print("Monitoring Active");
  }
}

// ---------------- WIFI ----------------
void connectWiFi() {
  Serial.print("Connecting to WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - start < 15000) {
    delay(300);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi connected. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi connection timed out; will retry later.");
  }
}

// ---------------- MQTT CONNECTION ----------------
void maintainMQTTConnection() {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) {
    return;
  }

  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) {
    return;
  }

  lastMqttAttempt = millis();

  String clientId = "SmartSewer-";
  clientId += String((uint32_t)ESP.getEfuseMac(), HEX);

  Serial.print("Connecting to MQTT... ");

  // Public broker test: no username/password.
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("connected");
  } else {
    Serial.print("failed, state=");
    Serial.println(mqttClient.state());
  }
}

// ---------------- MQTT PUBLISH ----------------
void publishSensorData() {
  if (!mqttClient.connected()) {
    Serial.println("MQTT not connected; publish skipped.");
    return;
  }

  char payload[512];

  snprintf(
    payload,
    sizeof(payload),
    "{"
      "\"zone1\":%.1f,"
      "\"zone2\":%.1f,"
      "\"zone3\":%.1f,"
      "\"flow\":%.2f,"
      "\"rain\":%.1f,"
      "\"gas_raw_adc\":%d,"
      "\"gas_label\":\"%s\","
      "\"worker_safety\":\"%s\","
      "\"blockageRisk\":%d,"
      "\"blockage_label\":\"%s\","
      "\"overflowRisk\":%d,"
      "\"overflow_label\":\"%s\","
      "\"suspectedArea\":\"%s\","
      "\"overallStatus\":\"%s\""
    "}",
    zone1, zone2, zone3,
    flowRate, rainIntensity, gasValue,
    gasStatus.c_str(),
    workerSafety.c_str(),
    blockageRisk, suspectedArea.c_str(),
    overflowRisk, overallStatus.c_str(),
    suspectedArea.c_str(),
    overallStatus.c_str()
  );

  if (mqttClient.publish(MQTT_TOPIC, payload)) {
    Serial.print("MQTT published: ");
    Serial.println(payload);
  } else {
    Serial.println("MQTT publish failed.");
  }
}

// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(TRIG1, OUTPUT);
  pinMode(ECHO1, INPUT);
  pinMode(TRIG2, OUTPUT);
  pinMode(ECHO2, INPUT);
  pinMode(TRIG3, OUTPUT);
  pinMode(ECHO3, INPUT);

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  analogReadResolution(12);

  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("SMART SEWER SYSTEM");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");

  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setKeepAlive(30);
  mqttClient.setSocketTimeout(5);
  mqttClient.setBufferSize(768);

  connectWiFi();

  Serial.println();
  Serial.println("SMART SEWER MONITORING");
  Serial.println("3 Zone Monitoring Active");
}

// ---------------- MAIN LOOP ----------------
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastWiFiRetry = 0;
    if (millis() - lastWiFiRetry >= 5000) {
      lastWiFiRetry = millis();
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }

  maintainMQTTConnection();
  mqttClient.loop();

  if (millis() - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = millis();

    zone1 = readWaterLevel(TRIG1, ECHO1);
delay(60);
zone2 = readWaterLevel(TRIG2, ECHO2);
delay(60);
zone3 = readWaterLevel(TRIG3, ECHO3);

flowRate = readFlowRate();
rainIntensity = readRainIntensity();
gasValue = readGasValue();

calculateRisks();

    bool gasDetected = gasValue >= GAS_ADC_THRESHOLD;
    digitalWrite(LED_PIN, gasDetected ? HIGH : LOW);
    digitalWrite(BUZZER_PIN, gasDetected ? HIGH : LOW);

    printReport();
    updateLCD();
    publishSensorData();
  }
}
