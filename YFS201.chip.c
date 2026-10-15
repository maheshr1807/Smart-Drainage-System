#include "wokwi-api.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct {
  pin_t out;
  uint32_t flowRate;
  timer_t timer;
} chip_state_t;


static void update_flow(void *user_data) {

  chip_state_t *chip = (chip_state_t *)user_data;

  // Read flow rate from slider
  float flow = attr_read_float(chip->flowRate);

  // Flow range: 0 - 10 L/min
  if (flow < 0.0f)
    flow = 0.0f;

  if (flow > 10.0f)
    flow = 10.0f;

  // Convert:
  // 0 L/min  -> 0V
  // 10 L/min -> 3.3V

  float voltage = (flow / 10.0f) * 3.3f;

  pin_dac_write(chip->out, voltage);

  printf("YFS201 Flow = %.2f L/min, Output = %.2f V\n",
         flow, voltage);
}


static void timer_callback(void *user_data) {
  update_flow(user_data);
}


void chip_init(void) {

  chip_state_t *chip = malloc(sizeof(chip_state_t));

  // Analog output
  chip->out = pin_init("OUT", ANALOG);

  // Float attribute
  chip->flowRate = attr_init_float("flowRate", 2.5f);

  // Timer
  const timer_config_t timer_config = {
    .callback = timer_callback,
    .user_data = chip,
  };

  chip->timer = timer_init(&timer_config);

  // Update every 100 ms
  timer_start(chip->timer, 100000, true);

  printf("YFS201 custom flow sensor initialized\n");
}