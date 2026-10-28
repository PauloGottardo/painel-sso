"""Cria o arquivo segobra.ico (capacete branco sobre fundo verde)."""
from PIL import Image, ImageDraw

T = 1024  # desenha grande e reduz depois, para as bordas ficarem suaves
VERDE = (46, 125, 50, 255)
BRANCO = (255, 255, 255, 255)

img = Image.new("RGBA", (T, T), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# fundo arredondado
d.rounded_rectangle([0, 0, T - 1, T - 1], radius=220, fill=VERDE)

# capacete: cúpula, aba e faixa central
d.pieslice([222, 310, 802, 890], 180, 360, fill=BRANCO)
d.rounded_rectangle([170, 590, 854, 690], radius=50, fill=BRANCO)
d.rectangle([482, 310, 542, 590], fill=VERDE)

img.save(
    "segobra.ico",
    sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
)
print("Ícone criado: segobra.ico")