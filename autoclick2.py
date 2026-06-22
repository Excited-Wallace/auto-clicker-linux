#!/usr/bin/env python3
import evdev
import time
import threading
import sys
import select
from evdev import UInput, ecodes as e

# ================= 状态与配置 =================
config = {
    'x': 940,
    'y': 453,
    'interval': 0.1
}

state = {
    'running': False,
    'config_mode': False
}
# ============================================

def setup_virtual_mouse():
    cap = {
        e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
        e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]
    }
    ui = UInput(cap, name="Wayland-Safe-Relative-Mouse", vendor=0x046d, product=0xc077, bustype=e.BUS_USB)
    time.sleep(1)
    return ui

def move_mouse_relative(ui, dx, dy):
    CHUNK = 50
    if dx != 0:
        steps = abs(dx) // CHUNK
        rem = abs(dx) % CHUNK
        sign = 1 if dx > 0 else -1
        for _ in range(steps):
            ui.write(e.EV_REL, e.REL_X, CHUNK * sign)
            ui.syn()
            time.sleep(0.001)
        if rem != 0:
            ui.write(e.EV_REL, e.REL_X, rem * sign)
            ui.syn()

    if dy != 0:
        steps = abs(dy) // CHUNK
        rem = abs(dy) % CHUNK
        sign = 1 if dy > 0 else -1
        for _ in range(steps):
            ui.write(e.EV_REL, e.REL_Y, CHUNK * sign)
            ui.syn()
            time.sleep(0.001)
        if rem != 0:
            ui.write(e.EV_REL, e.REL_Y, rem * sign)
            ui.syn()

def go_to_target(ui):
    move_mouse_relative(ui, -6000, -6000)
    time.sleep(0.05)
    move_mouse_relative(ui, config['x'], config['y'])

def click_worker(ui):
    while True:
        if state['running']:
            # 移除了这里的 go_to_target，只保留纯粹的点击动作
            ui.write(e.EV_KEY, e.BTN_LEFT, 1)
            ui.syn()
            ui.write(e.EV_KEY, e.BTN_LEFT, 0)
            ui.syn()
        time.sleep(config['interval'])

def print_menu():
    print(f"\n>> 当前坐标: ({config['x']}, {config['y']})")
    print(">> 操作说明: [F9]更改坐标 | [F10]测试定位 | [F12]定位并开始连点 | [F8]停止连点 | [Ctrl+C]退出")

def main():
    print(">> 初始化安全型相对虚拟鼠标...")
    ui = setup_virtual_mouse()

    worker = threading.Thread(target=click_worker, args=(ui,), daemon=True)
    worker.start()

    kbds = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities()
        if e.EV_KEY in caps and (e.KEY_F12 in caps[e.EV_KEY] or e.KEY_F9 in caps[e.EV_KEY]):
            kbds.append(dev)

    if not kbds:
        print("错误：未找到符合的键盘设备。")
        sys.exit(1)

    kbds_dict = {dev.fd: dev for dev in kbds}
    print_menu()

    try:
        while True:
            r, w, x = select.select([sys.stdin.fileno()] + list(kbds_dict.keys()), [], [])

            for fd in r:
                if fd == sys.stdin.fileno():
                    line = sys.stdin.readline().strip()
                    if state['config_mode']:
                        if line:
                            try:
                                parts = line.replace(',', ' ').split()
                                if len(parts) >= 2:
                                    config['x'] = int(parts[0])
                                    config['y'] = int(parts[1])
                                    print(f"\n[成功] 坐标已更新为: ({config['x']}, {config['y']})")
                                    state['config_mode'] = False
                                    print_menu()
                                else:
                                    print("格式不完整。请重新输入(例如: 1885 900)，或按 F9 取消：", end="", flush=True)
                            except ValueError:
                                print("格式错误。请输入纯数字(例如: 1885 900)，或按 F9 取消：", end="", flush=True)
                        else:
                            print("请输入新坐标，或按 F9 取消：", end="", flush=True)

                else:
                    for event in kbds_dict[fd].read():
                        if event.type == e.EV_KEY and event.value == 1:
                            if state['config_mode']:
                                if event.code == e.KEY_F9:
                                    state['config_mode'] = False
                                    print("\n\n[F9] 已取消坐标修改，返回主界面。")
                                    print_menu()
                            else:
                                if event.code == e.KEY_F12:
                                    if not state['running']:
                                        # 在启动连点时，执行单次定位校准
                                        print(f"\n[F12] 正在定位至 ({config['x']}, {config['y']}) 并启动连点...")
                                        go_to_target(ui)
                                        state['running'] = True
                                elif event.code == e.KEY_F8:
                                    if state['running']:
                                        state['running'] = False
                                        print("\n[F8] 连点已停止")
                                elif event.code == e.KEY_F10:
                                    print(f"\n[F10] 测试定位：归零并移动到 ({config['x']}, {config['y']})")
                                    go_to_target(ui)
                                elif event.code == e.KEY_F9:
                                    state['running'] = False
                                    state['config_mode'] = True
                                    print("\n[F9] 进入坐标修改模式。")
                                    print("请输入新的 X 和 Y 坐标 (空格分隔，例如 1885 900) 并按回车确认。")
                                    print("如需取消修改，请再次按 F9 : ", end="", flush=True)

    except KeyboardInterrupt:
        print("\n>> 程序已退出")
        ui.close()

if __name__ == "__main__":
    main()
