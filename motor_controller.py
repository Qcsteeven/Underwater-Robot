# motor_controller.py

import pigpio
from config import PI_HOST, MOTOR_PINS, STOP, MAX_UP, MAX_DOWN, \
    DEAD_ZONE, TRIGGER_DEAD_ZONE, HORIZONTAL_RAMP_STEP, VERTICAL_RAMP_STEP

class UnderwaterVehicleController:
    def __init__(self, pi_host=PI_HOST):
        self.pi = pigpio.pi(pi_host)
        if not self.pi.connected:
            raise ConnectionError(f"Не удалось подключиться к Raspberry Pi: {pi_host}")

        self.current_pwm = {name: STOP for name in MOTOR_PINS}
        for pin in MOTOR_PINS.values():
            self.pi.set_servo_pulsewidth(pin, STOP)

        print("✅ Контроллер моторов инициализирован")

    def _apply_ramp(self, current, target, ramp_step):
        if abs(target - current) <= ramp_step:
            return target
        return current + ramp_step if target > current else current - ramp_step

    def _stick_to_target_pwm(self, stick_value):
        if abs(stick_value) < DEAD_ZONE:
            return STOP
        sign = 1 if stick_value > 0 else -1
        power = abs(stick_value)
        pwm = STOP + sign * power * (MAX_UP - STOP)
        return max(MAX_DOWN, min(MAX_UP, int(pwm)))

    def _trigger_to_target_pwm(self, trigger_value, is_up):
        if trigger_value < TRIGGER_DEAD_ZONE:
            return STOP
        power = trigger_value ** 2
        if is_up:
            pwm = STOP + power * (MAX_UP - STOP)
        else:
            pwm = STOP - power * (STOP - MAX_DOWN)
        return int(pwm)

    def set_motor(self, name, pwm):
        pin = MOTOR_PINS[name]
        self.pi.set_servo_pulsewidth(pin, pwm)

    def stop_all(self):
        for name in self.current_pwm:
            self.current_pwm[name] = STOP
            self.set_motor(name, STOP)

    def update_from_gamepad(self, left_x, left_y, lt, rt, right_x):
        # Горизонтальное движение (оставляем без изменений)
        forward_input = -left_y
        turn_input = left_x
        left_cmd = forward_input - turn_input
        right_cmd = forward_input + turn_input

        max_cmd = max(abs(left_cmd), abs(right_cmd), 1e-6)
        if max_cmd > 1.0:
            left_cmd /= max_cmd
            right_cmd /= max_cmd

        target_left = self._stick_to_target_pwm(left_cmd)
        target_right = self._stick_to_target_pwm(right_cmd)
 
        # === Основная вертикальная тяга от триггеров (lt/rt) ===
        if rt > lt:
            base_vertical = self._trigger_to_target_pwm(rt, is_up=True)
        elif lt > rt:
            base_vertical = self._trigger_to_target_pwm(lt, is_up=False)
        else:
            base_vertical = STOP

        # === Дополнительное дифференциальное управление от right_x ===
        if abs(right_x) < DEAD_ZONE:
            diff_left = 0
            diff_right = 0
        else:
            # Только вверх (как в оригинальной логике триггеров)
            power = abs(right_x) ** 2
            diff_pwm = power * (MAX_UP - STOP)  # только положительное отклонение (вверх)

            if right_x > 0:
                diff_left = diff_pwm
                diff_right = 0
            else:
                diff_left = 0
                diff_right = diff_pwm

        # === Комбинируем базовую тягу и дифференциальный сигнал ===
        target_vertical_left = base_vertical + diff_left
        target_vertical_right = base_vertical + diff_right

        # Ограничиваем итоговые значения
        target_vertical_left = max(MAX_DOWN, min(MAX_UP, int(target_vertical_left)))
        target_vertical_right = max(MAX_DOWN, min(MAX_UP, int(target_vertical_right)))

        # Применяем плавный переход (ramp)
        self.current_pwm['motor_left'] = self._apply_ramp(
            self.current_pwm['motor_left'], target_left, HORIZONTAL_RAMP_STEP
        )
        self.current_pwm['motor_right'] = self._apply_ramp(
            self.current_pwm['motor_right'], target_right, HORIZONTAL_RAMP_STEP
        )
        self.current_pwm['motor_up_down_left'] = self._apply_ramp(
            self.current_pwm['motor_up_down_left'], target_vertical_left, VERTICAL_RAMP_STEP
        )
        self.current_pwm['motor_up_down_right'] = self._apply_ramp(
            self.current_pwm['motor_up_down_right'], target_vertical_right, VERTICAL_RAMP_STEP
        )

        # Отправляем PWM на моторы
        for name, pwm in self.current_pwm.items():
            self.set_motor(name, int(pwm))

    def cleanup(self):
        print("\n🛑 Остановка всех моторов...")
        self.stop_all()
        self.pi.stop()
        print("✅ Соединение закрыто")