#include <Arduino.h>

const int LEFT_Y  = 32;
const int LEFT_X  = 33;
const int RIGHT_Y = 34;
const int RIGHT_X = 35;

const int BUTTON_1 = 25;
const int BUTTON_2 = 26;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_1, INPUT_PULLUP);
  pinMode(BUTTON_2, INPUT_PULLUP);
}

void loop() {
  int leftX = analogRead(LEFT_X);
  int leftY = analogRead(LEFT_Y);
  int rightX = analogRead(RIGHT_X);
  int rightY = analogRead(RIGHT_Y);
  bool button1 = digitalRead(BUTTON_1) == LOW;
  bool button2 = digitalRead(BUTTON_2) == LOW;

  Serial.print("LeftXY: ");
  Serial.print(leftX);
  Serial.print(", ");
  Serial.print(leftY);
  Serial.print("    RightXY: ");
  Serial.print(rightX);
  Serial.print(", ");
  Serial.print(rightY);
  Serial.print("    Buttons: ");
  Serial.print(button1);
  Serial.print(", ");
  Serial.println(button2);

  // Faster updates make aiming smoother and capture shorter button presses.
  delay(10);
}
