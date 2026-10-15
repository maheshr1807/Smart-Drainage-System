#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WiFiClient.h>

// GLOBAL VARIABLES
unsigned long previousTime = 0;
unsigned long lastSendTime = 0; 

// PIN DEFINITIONS
#define TRIG_1 5
#define ECHO_1 18
#define TRIG_2 16
#define ECHO_2 17
#define TRIG_3 19
#define ECHO_3 23
#define FLOW_SENSOR_PIN 34
#define RAIN_SENSOR_PIN 35
#define MQ2_AO_PIN 32
#define LED_PIN 25
#define BUZZER_PIN 26
#define GAS_THRESHOLD 1000

// LCD
LiquidCrystal_I2C lcd(0x27, 20, 4);

// SYSTEM SETTINGS
const float SEWER_DEPTH = 100.0;

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

const char* SERVER_URL =
    "https://scribble-duplicate-ditto.ngrok-free.dev/sensors";

// THRESHOLDS
const float WATER_WARNING = 70.0;
const float WATER_CRITICAL = 90.0;
const float LOW_FLOW = 2.0;
const float RAIN_WARNING = 60.0;
const float RAIN_HEAVY = 80.0;

// VARIABLES
float waterLevel1 = 0.0;
float waterLevel2 = 0.0;
float waterLevel3 = 0.0;

float previousLevel1 = 0.0;
float previousLevel2 = 0.0;
float previousLevel3 = 0.0;

float riseRate1 = 0.0;
float riseRate2 = 0.0;
float riseRate3 = 0.0;

float flowRate = 0.0;
float rainIntensity = 0.0;

int gasValue = 0;

bool gasDetected = false;
bool firstReading = true;

int blockageRisk = 0;
int overflowRisk = 0;

String blockageLocation = "NONE";
String workerSafety = "SAFE";


const unsigned long SENSOR_INTERVAL = 2000;

// READ FLOW SENSOR
float readFlowRate() {
  int rawValue = analogRead(FLOW_SENSOR_PIN);
  float flow = (rawValue / 4095.0) * 10.0;

  if (flow < 0) flow = 0;
  if (flow > 10) flow = 10;

  return flow;
}

// READ RAIN SENSOR
float readRainIntensity() {
  int rawValue = analogRead(RAIN_SENSOR_PIN);
  float rain = (rawValue / 4095.0) * 100.0;

  if (rain < 0) rain = 0;
  if (rain > 100) rain = 100;

  return rain;
}

// READ HC-SR04 DISTANCE
float readDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration == 0) {
    return -1;
  }

  return duration / 58.0;
}

// DISTANCE TO WATER LEVEL
float distanceToWaterLevel(float distance) {
  if (distance < 0) {
    return 0;
  }

  float level =
    ((SEWER_DEPTH - distance) / SEWER_DEPTH) * 100.0;

  if (level < 0) level = 0;
  if (level > 100) level = 100;

  return level;
}

// READ ZONES
float readZone1() {
  return distanceToWaterLevel(readDistance(TRIG_1, ECHO_1));
}

float readZone2() {
  return distanceToWaterLevel(readDistance(TRIG_2, ECHO_2));
}

float readZone3() {
  return distanceToWaterLevel(readDistance(TRIG_3, ECHO_3));
}

// GAS DETECTION
void checkGas() {
  gasValue = analogRead(MQ2_AO_PIN);

  Serial.println();
  Serial.println("----- MQ-2 DEBUG -----");
  Serial.print("MQ2 RAW ADC : ");
  Serial.println(gasValue);
  Serial.print("Threshold   : ");
  Serial.println(GAS_THRESHOLD);

  gasDetected = (gasValue >= GAS_THRESHOLD);

  Serial.print("Gas Status  : ");
  Serial.println(gasDetected ? "GAS DETECTED" : "NORMAL");
  Serial.println("----------------------");
}

// CALCULATE WATER RISE RATE
float calculateRiseRate(
  float currentLevel,
  float oldLevel,
  float elapsedMinutes
) {
  if (elapsedMinutes <= 0) {
    return 0;
  }

  float difference = currentLevel - oldLevel;

  if (difference <= 0) {
    return 0;
  }

  return difference / elapsedMinutes;
}

// FIND HIGHEST WATER LEVEL ZONE
int findHighestZone() {
  if (waterLevel1 >= waterLevel2 &&
      waterLevel1 >= waterLevel3) {
    return 1;
  }

  if (waterLevel2 >= waterLevel1 &&
      waterLevel2 >= waterLevel3) {
    return 2;
  }

  return 3;
}

// BLOCKAGE DETECTION
void detectBlockage() {
  if (firstReading) {
    blockageRisk = 0;
    blockageLocation = "NONE";
    return;
  }

  int zone = findHighestZone();

  float highestLevel = 0;
  float highestRise = 0;

  if (zone == 1) {
    highestLevel = waterLevel1;
    highestRise = riseRate1;
  } else if (zone == 2) {
    highestLevel = waterLevel2;
    highestRise = riseRate2;
  } else {
    highestLevel = waterLevel3;
    highestRise = riseRate3;
  }

  int score = 0;

  // HIGH WATER
  if (highestLevel >= 90) {
    score += 40;
  } else if (highestLevel >= 70) {
    score += 30;
  } else if (highestLevel >= 50) {
    score += 15;
  }

  // FAST RISE
  if (highestRise >= 3.0) {
    score += 30;
  } else if (highestRise >= 1.0) {
    score += 20;
  } else if (highestRise >= 0.3) {
    score += 10;
  }

  // LOW FLOW
  if (flowRate < 0.5) {
    score += 20;
  } else if (flowRate < LOW_FLOW) {
    score += 15;
  }

  // LOW RAIN
  if (rainIntensity < 30) {
    score += 10;
  }

  // HEAVY RAIN REDUCES BLOCKAGE CONFIDENCE
  if (rainIntensity >= RAIN_HEAVY) {
    score -= 15;
  }

  if (score < 0) score = 0;
  if (score > 100) score = 100;

  blockageRisk = score;

  // SUSPECTED BLOCKAGE LOCATION
  if (blockageRisk < 50) {
    blockageLocation = "NONE";
  } else {
    if (zone == 1 &&
        waterLevel1 >= 70 &&
        waterLevel2 < 60) {
      blockageLocation = "BETWEEN Z1-Z2";
    } else if (zone == 2 &&
               waterLevel2 >= 70 &&
               waterLevel3 < 60) {
      blockageLocation = "BETWEEN Z2-Z3";
    } else if (zone == 3 && waterLevel3 >= 70) {
      blockageLocation = "NEAR OUTLET";
    } else if (zone == 1) {
      blockageLocation = "NEAR ZONE 1";
    } else if (zone == 2) {
      blockageLocation = "NEAR ZONE 2";
    } else {
      blockageLocation = "NEAR ZONE 3";
    }
  }
}

// OVERFLOW RISK
void calculateOverflowRisk() {
  float highestWater = max(
    waterLevel1,
    max(waterLevel2, waterLevel3)
  );

  float highestRise = max(
    riseRate1,
    max(riseRate2, riseRate3)
  );

  int score = 0;

  if (highestWater >= 90) {
    score += 60;
  } else if (highestWater >= 70) {
    score += 45;
  } else if (highestWater >= 50) {
    score += 25;
  }

  if (rainIntensity >= 80) {
    score += 25;
  } else if (rainIntensity >= 60) {
    score += 15;
  }

  if (highestRise >= 3.0) {
    score += 20;
  } else if (highestRise >= 1.0) {
    score += 10;
  }

  if (score > 100) score = 100;

  overflowRisk = score;
}

// WORKER SAFETY
void determineWorkerSafety() {
  float highestWater = max(
    waterLevel1,
    max(waterLevel2, waterLevel3)
  );

  if (gasDetected) {
    workerSafety = "DO NOT ENTER";
  } else if (highestWater >= WATER_CRITICAL) {
    workerSafety = "DO NOT ENTER";
  } else if (blockageRisk >= 70) {
    workerSafety = "CAUTION";
  } else {
    workerSafety = "SAFE";
  }
}

// ALARM SYSTEM
void alarmSystem() {
  bool critical =
    gasDetected ||
    blockageRisk >= 80 ||
    overflowRisk >= 80;

  bool warning =
    blockageRisk >= 50 ||
    overflowRisk >= 50;

  if (critical) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
  } else if (warning) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
  } else {
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// LCD DISPLAY
void updateLCD() {
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("L1:");
  lcd.print(waterLevel1, 0);
  lcd.print("% L2:");
  lcd.print(waterLevel2, 0);
  lcd.print("%");

  lcd.setCursor(0, 1);
  lcd.print("L3:");
  lcd.print(waterLevel3, 0);
  lcd.print("% F:");
  lcd.print(flowRate, 1);

  lcd.setCursor(0, 2);
  lcd.print("Rain:");
  lcd.print(rainIntensity, 0);
  lcd.print("% G:");

  if (gasDetected) {
    lcd.print("HIGH");
  } else {
    lcd.print("OK");
  }

  lcd.setCursor(0, 3);

  if (blockageRisk >= 50) {
    lcd.print("BLK:");
    lcd.print(blockageRisk);
    lcd.print("%");
  } else {
    lcd.print("STATUS: NORMAL");
  }
}

// SERIAL MONITOR
void printSerialData() {
  Serial.println();
  Serial.println("========================================");
  Serial.println("       SMART SEWER MONITORING");
  Serial.println("========================================");

  Serial.println();
  Serial.println("WATER LEVEL");

  Serial.print("Zone 1 (0m)   : ");
  Serial.print(waterLevel1, 1);
  Serial.println(" %");

  Serial.print("Zone 2 (50m)  : ");
  Serial.print(waterLevel2, 1);
  Serial.println(" %");

  Serial.print("Zone 3 (100m) : ");
  Serial.print(waterLevel3, 1);
  Serial.println(" %");

  Serial.println();
  Serial.println("WATER RISE RATE");

  Serial.print("Zone 1 : ");
  Serial.print(riseRate1, 2);
  Serial.println(" %/min");

  Serial.print("Zone 2 : ");
  Serial.print(riseRate2, 2);
  Serial.println(" %/min");

  Serial.print("Zone 3 : ");
  Serial.print(riseRate3, 2);
  Serial.println(" %/min");

  Serial.println();
  Serial.print("Flow Rate      : ");
  Serial.print(flowRate, 2);
  Serial.println(" L/min");

  Serial.print("Rain Intensity : ");
  Serial.print(rainIntensity, 1);
  Serial.println(" %");

  Serial.print("MQ-2 Value     : ");
  Serial.println(gasValue);

  Serial.print("Gas Status     : ");
  Serial.println(gasDetected ? "GAS DETECTED" : "NORMAL");

  Serial.println();
  Serial.print("Blockage Risk  : ");
  Serial.print(blockageRisk);
  Serial.println(" %");

  Serial.print("Suspected Area : ");
  Serial.println(blockageLocation);

  Serial.print("Overflow Risk  : ");
  Serial.print(overflowRisk);
  Serial.println(" %");

  Serial.print("Worker Safety  : ");
  Serial.println(workerSafety);

  Serial.println();
  Serial.print("Overall Status : ");

  if (gasDetected) {
    Serial.println("CRITICAL - GAS HAZARD");
  } else if (blockageRisk >= 80) {
    Serial.println("CRITICAL - BLOCKAGE");
  } else if (overflowRisk >= 80) {
    Serial.println("CRITICAL - OVERFLOW");
  } else if (blockageRisk >= 50 || overflowRisk >= 50) {
    Serial.println("WARNING");
  } else {
    Serial.println("NORMAL");
  }

  Serial.println("========================================");
}

// SEND SENSOR DATA TO FLASK





void sendSensorData() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected - data not sent");
    return;
  }

  WiFiClientSecure client;
  client.setInsecure();  // Demo/testing only

  HTTPClient http;
  http.setConnectTimeout(15000);
  http.setTimeout(15000);
  http.setReuse(false);

  Serial.println("\nSending sensor data to Flask...");
  Serial.println(SERVER_URL);

  if (!http.begin(client, SERVER_URL)) {
    Serial.println("HTTPS initialization failed");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("ngrok-skip-browser-warning", "true");

  String payload = "{";
  payload += "\"zone1\":" + String(waterLevel1, 1) + ",";
  payload += "\"zone2\":" + String(waterLevel2, 1) + ",";
  payload += "\"zone3\":" + String(waterLevel3, 1) + ",";
  payload += "\"flow\":" + String(flowRate, 2) + ",";
  payload += "\"rain\":" + String(rainIntensity, 1) + ",";
  payload += "\"gas\":" + String(gasValue);
  payload += "}";

  Serial.println("Payload:");
  Serial.println(payload);

  int code = http.POST(payload);

  Serial.printf("Receiver HTTP status: %d\n", code);

  if (code >= 200 && code < 300) {
    Serial.println("SUCCESS: Sensor data sent!");
    Serial.println(http.getString());
  } else {
    Serial.println("FAILED: Sensor data not confirmed");

    if (code < 0) {
      Serial.println(http.errorToString(code));
    } else {
      Serial.println(http.getString());
    }
  }

  http.end();
}





//void testHTTPS() {
  WiFiClientSecure client;
  client.setInsecure();  // Testing only

  HTTPClient https;
  https.setConnectTimeout(15000);
  https.setTimeout(15000);
  https.setReuse(false);

  const char* url =
      "https://scribble-duplicate-ditto.ngrok-free.dev/health";

  Serial.println("TEST: SECURE CLIENT + HTTPS URL");

  if (!https.begin(client, url)) {
    Serial.println("HTTPS begin failed");
    return;
  }

  https.addHeader("ngrok-skip-browser-warning", "true");

  int code = https.GET();
  Serial.printf("HTTPS status: %d\n", code);

  if (code > 0) {
    Serial.println(https.getString());
  } else {
    Serial.println(https.errorToString(code));
  }

  https.end();
}

  
void printDatasetRow() {
  Serial.print("DATASET,");
  Serial.print(waterLevel1, 1); Serial.print(",");
  Serial.print(waterLevel2, 1); Serial.print(",");
  Serial.print(waterLevel3, 1); Serial.print(",");
  Serial.print(flowRate, 2); Serial.print(",");
  Serial.print(rainIntensity, 1); Serial.print(",");
  Serial.print(gasValue); Serial.print(",");
  Serial.print(blockageRisk >= 50 ? 1 : 0); Serial.print(",");
  Serial.print(overflowRisk >= 50 ? 1 : 0); Serial.print(",");
  Serial.println(gasDetected ? 1 : 0);
}




// SETUP
void setup() {
  Serial.begin(115200);

  // CONNECT TO WOKWI WIFI
 WiFi.mode(WIFI_STA);
 WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6); 

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");
  //testNgrokHttp();
  Serial.print("DNS result: ");
Serial.println(
    WiFi.hostByName("example.com", *(new IPAddress()))
);
  //testHTTPS();

  //if (WiFi.status() == WL_CONNECTED) {
  testGenericHttps();
}

  Serial.println("############################");
  Serial.println("ESP32 SERIAL TEST");
  Serial.println("ESP32 IS RUNNING");
  Serial.println("############################");

  // HC-SR04
  pinMode(TRIG_1, OUTPUT);
  pinMode(ECHO_1, INPUT);

  pinMode(TRIG_2, OUTPUT);
  pinMode(ECHO_2, INPUT);

  pinMode(TRIG_3, OUTPUT);
  pinMode(ECHO_3, INPUT);

  digitalWrite(TRIG_1, LOW);
  digitalWrite(TRIG_2, LOW);
  digitalWrite(TRIG_3, LOW);

  // ANALOG SENSORS
  pinMode(FLOW_SENSOR_PIN, INPUT);
  pinMode(RAIN_SENSOR_PIN, INPUT);
  pinMode(MQ2_AO_PIN, INPUT);

  // OUTPUTS
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();

  lcd.setCursor(2, 1);
  lcd.print("SMART SEWER");

  lcd.setCursor(2, 2);
  lcd.print("MONITORING");

  delay(2000);
  lcd.clear();

  Serial.println();
  Serial.println("================================");
  Serial.println(" SMART SEWER MONITORING SYSTEM");
  Serial.println("================================");
  Serial.println("System Started");
  Serial.println("3 Zone Monitoring Active");
  Serial.println();
}



// MAIN LOOP
void loop() {
  unsigned long currentTime = millis();

  if (currentTime - previousTime >= SENSOR_INTERVAL) {
    previousTime = currentTime;

    // SAVE PREVIOUS WATER LEVELS
    previousLevel1 = waterLevel1;
    previousLevel2 = waterLevel2;
    previousLevel3 = waterLevel3;

    // READ WATER LEVELS
    waterLevel1 = readZone1();
    delay(100);

    waterLevel2 = readZone2();
    delay(100);

    waterLevel3 = readZone3();

    // READ OTHER SENSORS
    flowRate = readFlowRate();
    rainIntensity = readRainIntensity();
    checkGas();

    // CALCULATE WATER RISE RATE
    if (firstReading) {
      riseRate1 = 0;
      riseRate2 = 0;
      riseRate3 = 0;
    } else {
      float elapsedMinutes = SENSOR_INTERVAL / 60000.0;

      riseRate1 = calculateRiseRate(
        waterLevel1, previousLevel1, elapsedMinutes
      );

      riseRate2 = calculateRiseRate(
        waterLevel2, previousLevel2, elapsedMinutes
      );

      riseRate3 = calculateRiseRate(
        waterLevel3, previousLevel3, elapsedMinutes
      );
    }

    // DETECTION AND SAFETY
    detectBlockage();
    calculateOverflowRisk();
    determineWorkerSafety();
    alarmSystem();

    // UPDATE LCD AND SERIAL MONITOR
    updateLCD();
    printSerialData();
    printDatasetRow();

    // SEND SENSOR DATA TO FLASK EVERY 5 SECONDS
    if (millis() - lastSendTime >= 5000) {
      lastSendTime = millis();
      sendSensorData();
    }

    // MARK FIRST READING COMPLETE
    firstReading = false;
  }
}



//void testGenericHttps() {
  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.setConnectTimeout(15000);
  http.setTimeout(15000);

  Serial.println("TEST: NGROK HTTPS");

  if (!http.begin(
        client,
        "https://scribble-duplicate-ditto.ngrok-free.dev/health"
      )) {
    Serial.println("HTTPS begin failed");
    return;
  }

  http.addHeader("ngrok-skip-browser-warning", "true");

  int code = http.GET();

  Serial.printf("ngrok HTTPS status: %d\n", code);

  if (code > 0) {
    Serial.println(http.getString());
  } else {
    Serial.println(http.errorToString(code));
  }

  http.end();
}



//void testNgrokHttp() {
  WiFiClient client;
  HTTPClient http;

  http.setConnectTimeout(15000);
  http.setTimeout(15000);

  Serial.println("TEST: NGROK HTTP");

  if (!http.begin(
        client,
        "http://scribble-duplicate-ditto.ngrok-free.dev/health"
      )) {
    Serial.println("HTTP begin failed");
    return;
  }

  int code = http.GET();

  Serial.printf("ngrok HTTP status: %d\n", code);

  if (code > 0) {
    Serial.println(http.getString());
  } else {
    Serial.println(http.errorToString(code));
  }

  http.end();
}
