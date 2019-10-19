#!/usr/bin/env python3
import sys
import argparse
from random import randint
from time import time, sleep
from os import environ

environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
environ["SDL_VIDEO_CENTERED"] = "1"
import pygame
from pygame import HWSURFACE, DOUBLEBUF


class Chip8:
    def __init__(self, scale=10, color="white", error=False, log=False):
        self.scale = scale
        if color in pygame.color.THECOLORS:
            self.color = pygame.color.THECOLORS[color]
        else:
            self.color = pygame.color.THECOLORS["white"]
        self.error = error
        self.log = log

        self.opcode = Short(0)
        self.I = Short(0)
        self.pc = Short(0x200)

        self.memory = [Byte(0) for _ in range(4096)]
        self.V = [Byte(0) for _ in range(16)]

        self.stack = [Short(0) for _ in range(16)]
        self.sp = Byte(0)

        self.gfx = [Byte(0) for _ in range(64*32)]
        self.key = [0 for _ in range(17)]
        self.key[0x10] = 0x10

        self.delay_timer = Byte(0)
        self.sound_timer = Byte(0)

        chip8_font = [
            0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
            0x20, 0x60, 0x20, 0x20, 0x70,  # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
            0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
            0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
            0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
            0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
            0xF0, 0x80, 0xF0, 0x80, 0x80   # F
        ]

        for i in range(80):
            self.memory[i].set(chip8_font[i])

        pygame.display.set_caption("CHIP-8")
        display = pygame.display.set_mode(
            (self.scale * 64, self.scale * 32),
            HWSURFACE|DOUBLEBUF
        )
        self.pxarray = pygame.PixelArray(display)
        self.pxarray[:] = pygame.color.THECOLORS["black"]

        self.game_keys = {
            pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
            pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
            pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
            pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF
        }

    def load(self, rom):
        pygame.display.set_caption("CHIP-8 - {}".format(
            rom.split("/")[-1].split(".")[0])
        )
        with open(rom, "rb") as file:
            i = 0
            byte = file.read(1)
            while byte:
                self.memory[i + 0x200].set(
                    int.from_bytes(byte, byteorder="big", signed=False)
                )
                byte = file.read(1)
                i += 1

    def emulate_cycle(self):
        self.opcode.set(
            (Short(self.memory[self.pc]) << 8) | self.memory[self.pc + 1]
        )

        op = Byte((self.opcode & 0xF000) >> 12)
        nnn = Short(self.opcode & 0x0FFF)
        n = Byte(self.opcode & 0x000F)
        x = Byte((self.opcode & 0x0F00) >> 8)
        y = Byte((self.opcode & 0x00F0) >> 4)
        kk = Byte(self.opcode & 0x00FF)

        if self.log:
            print("OPCODE: {0:<6} I: {1:4d} PC: {2:4d} V: [{3}] STACK: [{4}]"
                .format(
                    "0x{:X}".format(int(self.opcode)),
                    int(self.I),
                    int(self.pc),
                    " ".join(["{:3d}".format(int(x)) for x in self.V]),
                    " ".join(["{:4d}".format(int(x)) for x in self.stack])
                )
            )

        if op == 0x0:
            # 00E0: Clear the display
            if kk == 0xE0:
                self.gfx = [Byte(0) for _ in range(64*32)]
                self.pxarray[:] = pygame.color.THECOLORS["black"]

            # 00EE: Return from a subroutine
            elif kk == 0xEE:
                self.sp -= 1
                self.pc.set(self.stack[self.sp])

            # Unknown opcode [0x0000]
            else:
                if self.error:
                    print("Unknown opcode [0x0000]: 0x{:X}".format(
                        int(self.opcode))
                    )

        # 1nnn: Jump to location nnn
        elif op == 0x1:
            self.pc.set(nnn - 2)

        # 2nnn: Call subroutine at nnn
        elif op == 0x2:
            self.stack[self.sp].set(self.pc)
            self.sp += 1
            self.pc.set(nnn - 2)

        # 3xkk: Skip next instruction if Vx = kk
        elif op == 0x3:
            if self.V[x] == kk:
                self.pc += 2

        # 4xkk: Skip next instruction if Vx != kk
        elif op == 0x4:
            if self.V[x] != kk:
                self.pc += 2

        # 5xy0: Skip next instruction if Vx = Vy
        elif op == 0x5:
            if self.V[x] == self.V[y]:
                self.pc += 2

        # 6xkk: Set Vx = kk
        elif op == 0x6:
            self.V[x].set(kk)

        # 7xkk: Set Vx = Vx + kk
        elif op == 0x7:
            self.V[x] += kk

        elif op == 0x8:
            # 8xy0: Set Vx = Vy
            if n == 0x0:
                self.V[x].set(self.V[y])

            # 8xy1: Set Vx = Vx OR Vy
            elif n == 0x1:
                self.V[x].set(self.V[x] | self.V[y])

            # 8xy2: Set Vx = Vx AND Vy
            elif n == 0x2:
                self.V[x].set(self.V[x] & self.V[y])

            # 8xy3: Set Vx = Vx XOR Vy
            elif n == 0x3:
                self.V[x].set(self.V[x] ^ self.V[y])

            # 8xy4: Set Vx = Vx + Vy, set VF = carry
            elif n == 0x4:
                self.V[0xF].set(self.V[y] > (Byte(0xFF) - self.V[x]))
                self.V[x] += self.V[y]

            # 8xy5: Set Vx = Vx - Vy, set VF = NOT borrow
            elif n == 0x5:
                self.V[0xF].set(self.V[x] > self.V[y])
                self.V[x] -= self.V[y]

            # 8xy6: Set Vx = Vx SHR 1
            elif n == 0x6:
                self.V[0xF].set(self.V[x] & 0x0001)
                self.V[x] >>= 1

            # 8xy7: Set Vx = Vy - Vx, set VF = NOT borrow
            elif n == 0x7:
                self.V[0xF].set(self.V[y] > self.V[x])
                self.V[y] -= self.V[x]

            # 8xyE: Set Vx = Vx SHL 1
            elif n == 0xE:
                self.V[0xF].set(self.V[x] >> 7)
                self.V[x] <<= 1

            # Unknown opcode [0x8000]
            else:
                if self.error:
                    print("Unknown opcode [0x8000]: 0x{:X}".format(
                        int(self.opcode))
                    )

        # 9xy0: Skip next instruction if Vx != Vy
        elif op == 0x9:
            if self.V[x] != self.V[y]:
                self.pc += 2

        # Annn: Set I = nnn
        elif op == 0xA:
            self.I.set(nnn)

        # Bnnn: Jump to location nnn + V0
        elif op == 0xB:
            self.pc.set(nnn + self.V[0x0] - 2)

        # Cxkk: Set Vx = random byte AND kk
        elif op == 0xC:
            self.V[x].set(kk & randint(0, 255))

        # Dxyn: Display n-byte sprite starting at memory location I
        # at (Vx, Vy), set VF = collision
        elif op == 0xD:
            xx = Short(self.V[x])
            yy = Short(self.V[y])
            pixel = Short(0)

            self.V[0xF].set(0)
            for y_index in range(n):
                y_index = Short(y_index)
                pixel.set(self.memory[self.I + y_index])

                for x_index in range(8):
                    x_index = Short(x_index)
                    pos = (xx + x_index) % 64 + ((yy + y_index) % 32) * 64
                    if (pixel & (Short(0x80) >> x_index)) != 0:
                        if self.gfx[pos] == 1:
                            self.V[0xF].set(1)
                        self.gfx[pos] ^= 1

                        x_pos = ((xx+x_index) % 64) * self.scale
                        y_pos = ((yy+y_index) % 32) * self.scale
                        if self.gfx[pos] == 1:
                            self.pxarray[
                                x_pos : x_pos+self.scale,
                                y_pos : y_pos+self.scale
                            ] = self.color
                        else:
                            self.pxarray[
                                x_pos : x_pos+self.scale,
                                y_pos : y_pos+self.scale
                            ] = pygame.color.THECOLORS["black"]

        elif op == 0xE:
            # Ex9E: Skip next instruction if
            # key with the value of Vx is pressed
            if kk == 0x9E:
                if self.key[self.V[x]] != 0:
                    self.pc += 2

            # ExA1: Skip next instruction
            # if key with the value of Vx is not pressed
            elif kk == 0xA1:
                if self.key[self.V[x]] == 0:
                    self.pc += 2

            # Unknown opcode [0xE000]
            else:
                if self.error:
                    print("Unknown opcode [0xE000]: 0x{:X}".format(
                        int(self.opcode))
                    )

        elif op == 0xF:
            # Fx07: Set Vx = delay timer value
            if kk == 0x07:
                self.V[x].set(self.delay_timer)

            # Fx0A: Wait for a key press, store the value of the key in Vx
            elif kk == 0x0A:
                if self.key[0x10] < 0x10:
                    self.V[x].set(self.key[0x10])
                else:
                    self.pc -= 2

            # Fx15: Set delay timer = Vx
            elif kk == 0x15:
                self.delay_timer.set(self.V[x])

            # Fx18: Set sound timer = Vx
            elif kk == 0x18:
                self.sound_timer.set(self.V[x])

            # Fx1E: Set I = I + Vx
            elif kk == 0x1E:
                self.I += self.V[x]

            # Fx29: Set I = location of sprite for digit Vx
            elif kk == 0x29:
                self.I.set(Short(self.V[x]) * 5)

            # Fx33: Store BCD representation of Vx
            # in memory locations I, I+1, and I+2
            elif kk == 0x33:
                self.memory[self.I].set(self.V[x] // 100)
                self.memory[self.I+1].set((self.V[x] // 10) % 10)
                self.memory[self.I+2].set((self.V[x] % 100) % 10)

            # Fx55: Store registers V0 through Vx
            # in memory starting at location I
            elif kk == 0x55:
                for i in range(x+1):
                    self.memory[self.I+i].set(self.V[i])

            # Fx65: Read registers V0 through Vx from memory
            # starting at location I
            elif kk == 0x65:
                for i in range(x+1):
                    self.V[i].set(self.memory[int(self.I)+i])

            # Unknown opcode [0xF000]
            else:
                if self.error:
                    print("Unknown opcode [0xF000]: 0x{:X}".format(
                        int(self.opcode))
                    )

        # Unknown opcode
        else:
            if self.error:
                print("Unknown opcode: 0x{:X}".format(int(self.opcode)))

        self.pc += 2

        pressed_keys = pygame.key.get_pressed()
        for key, value in self.game_keys.items():
            self.key[value] = pressed_keys[key]

        self.key[0x10] = 0x10
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key in self.game_keys:
                    self.key[0x10] = self.game_keys[event.key]


class Byte:
    def __init__(self, n=0):
        self.n = (int(n) & 0xFF)

    def __int__(self):
        return int(self.n)

    def __index__(self):
        return int(self.n)

    def __repr__(self):
        return repr(self.n)

    def __add__(self, other):
        return Byte(self.n + int(other))

    def __sub__(self, other):
        return Byte(self.n - int(other))

    def __mul__(self, other):
        return Byte(self.n * int(other))

    def __floordiv__(self, other):
        return Byte(self.n // int(other))

    def __mod__(self, other):
        return Byte(self.n % int(other))

    def __lshift__(self, other):
        return Byte(self.n << int(other))

    def __rshift__(self, other):
        return Byte(self.n >> int(other))

    def __and__(self, other):
        return Byte(self.n & int(other))

    def __or__(self, other):
        return Byte(self.n | int(other))

    def __xor__(self, other):
        return Byte(self.n ^ int(other))

    def __lt__(self, other):
        return self.n < int(other)

    def __le__(self, other):
        return self.n <= int(other)

    def __eq__(self, other):
        return self.n == int(other)

    def __ne__(self, other):
        return self.n != int(other)

    def __gt__(self, other):
        return self.n > int(other)

    def __ge__(self, other):
        return self.n >= int(other)

    def set(self, n):
        self.__init__(n)


class Short:
    def __init__(self, n=0):
        self.n = (int(n) & 0xFFFF)

    def __int__(self):
        return int(self.n)

    def __index__(self):
        return int(self.n)

    def __repr__(self):
        return repr(self.n)

    def __add__(self, other):
        return Short(self.n + int(other))

    def __sub__(self, other):
        return Short(self.n - int(other))

    def __mul__(self, other):
        return Short(self.n * int(other))

    def __floordiv__(self, other):
        return Short(self.n // int(other))

    def __mod__(self, other):
        return Short(self.n % int(other))

    def __lshift__(self, other):
        return Short(self.n << int(other))

    def __rshift__(self, other):
        return Short(self.n >> int(other))

    def __and__(self, other):
        return Short(self.n & int(other))

    def __or__(self, other):
        return Short(self.n | int(other))

    def __xor__(self, other):
        return Short(self.n ^ int(other))

    def __lt__(self, other):
        return self.n < int(other)

    def __le__(self, other):
        return self.n <= int(other)

    def __eq__(self, other):
        return self.n == int(other)

    def __ne__(self, other):
        return self.n != int(other)

    def __gt__(self, other):
        return self.n > int(other)

    def __ge__(self, other):
        return self.n >= int(other)

    def set(self, n):
        self.__init__(n)


def main(args):
    chip8 = Chip8(args.scale, args.color, args.error, args.log)
    chip8.load(args.rom)
    last = time()

    while True:
        sleep(1/args.frequency)
        chip8.emulate_cycle()

        if time() - last >= 1/60:
            last = time()
            pygame.display.update()
            if chip8.delay_timer > 0:
                chip8.delay_timer -= 1
            if chip8.sound_timer > 0:
                if chip8.sound_timer == 1:
                    # print("BEEP")
                    pass
                chip8.sound_timer -= 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CHIP-8 interpreter")
    parser.add_argument("rom", help="path to file")
    parser.add_argument("-f", dest="frequency", type=int, default=500,
                        help="set CPU speed [Hz] (default: 500)")
    parser.add_argument("-s", dest="scale", type=int, default=10,
                        help="set display scale (default: 10)")
    parser.add_argument("-c", dest="color", type=str, default="white",
                        help="set display color (default: white)")
    parser.add_argument("--error", action="store_true",
                        help="show error messages")
    parser.add_argument("--log", action="store_true", help="show log")
    main(parser.parse_args())
