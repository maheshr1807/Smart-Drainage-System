#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct {
  pin_t out;
  uint32_t rainIntensity;
  timer_t timer;
} chip_state_t;


static void update_rain(void *user_data) {

  chip_state_t *chip = (chip_state_t *)user_data;

  // Read rain intensity from Wokwi control
  float rain = (float)attr_read(chip->rainIntensity);

  // Convert 0-100% to 0-3.3V
  float voltage = (rain / 100.0f) * 3.3f;

  // Keep voltage inside valid range
  if (voltage < 0)
    voltage = 0;

  if (voltage > 3.3f)
    voltage = 3.3f;

  pin_dac_write(chip->out, voltage);
}


static void timer_callback(void *user_data) {

  update_rain(user_data);

}


void chip_init(void) {

  chip_state_t *chip = malloc(sizeof(chip_state_t));

  // Analog output
  chip->out = pin_init("OUT", ANALOG);

  // Rain intensity attribute
  chip->rainIntensity = attr_init("rainIntensity", 20);

  // Timer
  const timer_config_t timer_config = {
    .callback = timer_callback,
    .user_data = chip,
  };

  chip->timer = timer_init(&timer_config);

  // Update every 100 ms
  timer_start(chip->timer, 100000, true);

  printf("YL83 custom rain sensor initialized\n");
}