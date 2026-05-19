import pygame, sys, time, datetime
from auth import verify_login
from abac_engine import check_access
from models.building import get_all
from models.user import toggle_shift


# Надёжная инициализация шрифта
def get_font(size, bold=False):
    fonts = ["Segoe UI", "Arial", "Helvetica", "DejaVu Sans", None]
    for f in fonts:
        try:
            return pygame.font.SysFont(f, size, bold=bold)
        except:
            continue
    return pygame.font.Font(None, size)


def scale_color(color: pygame.Color, factor: float) -> pygame.Color:
    """Масштабирует цвет на коэффициент (0.0 - 1.0)"""
    return pygame.Color(
        max(0, min(255, int(color.r * factor))),
        max(0, min(255, int(color.g * factor))),
        max(0, min(255, int(color.b * factor)))
    )


def parse_color(hex_str: str, default=(136, 136, 136)) -> tuple:
    """Безопасный парсинг цвета из БД: поддерживает #RGB и #RRGGBB"""
    try:
        h = hex_str.lstrip('#')
        if len(h) == 3:  # CSS shorthand #RGB -> #RRGGBB
            h = ''.join(c * 2 for c in h)
        if len(h) == 6:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except:
        pass
    return default


class SCUDClient:
    def __init__(self, user_data):
        pygame.init()
        self.W, self.H = 1100, 750
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("СКУД Критического Объекта (Pure SQL)")
        self.font = get_font(18)
        self.font_b = get_font(24, bold=True)
        self.clock = pygame.time.Clock()
        self.user = user_data
        self.last_eval = 0
        self.access_map = {}
        self.msg = ""
        self.msg_time = 0

    def draw_text(self, txt, f, col, x, y, c=False):
        try:
            s = f.render(txt, True, col)
            r = s.get_rect(center=(x, y) if c else (x, y))
            self.screen.blit(s, r)
        except:
            # Фоллбэк: рисуем прямоугольник вместо текста
            pygame.draw.rect(self.screen, col, (x, y - 10, len(txt) * 10, 20))

    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_s:
                        new = toggle_shift(self.user["id"])
                        self.user["shift_status"] = new
                        self.msg = f"✓ Смена: {new.upper()}"
                        self.msg_time = time.time()
                    if ev.key == pygame.K_ESCAPE:
                        running = False

            self.screen.fill((22, 25, 30))
            now = datetime.datetime.now()

            # Обновление доступа раз в секунду
            if time.time() - self.last_eval > 1.0:
                for b in get_all():
                    self.access_map[b["id"]] = check_access(self.user, b["id"])
                self.last_eval = time.time()

            # Header
            self.draw_text(
                f"👤 {self.user['username']} | {self.user['role_name']} | Смена: {self.user['shift_status'].upper()}",
                self.font, (200, 210, 220), 20, 20)
            self.draw_text(f"⏱ {now.strftime('%H:%M:%S')} | 📅 {now.strftime('%A')}",
                           self.font, (150, 160, 170), self.W - 20, 20)

            # Отрисовка зданий
            for b in get_all():
                acc = self.access_map.get(b["id"], False)
                base_rgb = parse_color(b["color_hex"])
                base = pygame.Color(*base_rgb)

                # Цвета граней: используем scale_color вместо умножения
                if acc:
                    top_col = base
                    left_col = scale_color(base, 0.75)
                    right_col = scale_color(base, 0.85)
                else:
                    # Затемняем недоступные здания
                    dark_factor = 0.35
                    top_col = scale_color(base, dark_factor)
                    left_col = scale_color(base, dark_factor * 0.7)
                    right_col = scale_color(base, dark_factor * 0.85)

                x, y, w, h, d = b["x"], b["y"], b["w"], b["h"], b["depth"]

                # Изометрические грани (псевдо-3D)
                try:
                    # Левая грань
                    pygame.draw.polygon(self.screen, left_col, [
                        (x, y), (x - d, y - d), (x - d, y + h - d), (x, y + h)
                    ])
                    # Правая грань
                    pygame.draw.polygon(self.screen, right_col, [
                        (x, y + h), (x + w, y + h), (x + w + d, y + h - d), (x - d, y + h - d)
                    ])
                    # Верхняя грань
                    pygame.draw.polygon(self.screen, top_col, [
                        (x, y), (x + w, y), (x + w + d, y - d), (x - d, y - d)
                    ])
                    # Контур
                    outline = (0, 0, 0) if not acc else (40, 40, 40)
                    pygame.draw.polygon(self.screen, outline, [
                        (x, y), (x + w, y), (x + w + d, y - d), (x - d, y - d)
                    ], 2)
                except Exception as e:
                    # Фоллбэк: простой прямоугольник
                    pygame.draw.rect(self.screen, base_rgb if acc else (80, 80, 80),
                                     (x - d, y - d, w + d * 2, h + d * 2))

                # Подписи
                status = "✅ ДОСТУП" if acc else "🔒 ЗАПРЕЩЕНО"
                col = (50, 255, 50) if acc else (255, 50, 50)
                self.draw_text(b["name"], self.font_b, (240, 240, 240), x + w // 2, y + h + 15)
                self.draw_text(status, self.font, col, x + w // 2, y + h + 40)

            # Сообщения
            if self.msg and time.time() - self.msg_time < 2.0:
                self.draw_text(self.msg, self.font, (255, 255, 100), self.W // 2, self.H - 40, True)

            self.draw_text("[S] Смена | [ESC] Выход", self.font, (100, 110, 120), self.W // 2, self.H - 20, True)

            pygame.display.flip()
            self.clock.tick(30)