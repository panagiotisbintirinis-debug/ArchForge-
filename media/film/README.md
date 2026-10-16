# ArchForge — ταινία εισαγωγής

`film.html`: η ταινία σε three.js (τοπίο, καμάρα που χτίζεται, σιδερένια πόρτα, σπίτι που μεγαλώνει, τίτλος).
Ανοίγει σε browser και παίζει· `?w=1080&h=1920` για κάθετη (Instagram), `?w=1920&h=1080` για οριζόντια.

Εγγραφή σε MP4 (Node + Playwright + ffmpeg):

```
mkdir frames
node capture.js video 1080 1920            # καρέ 30 fps σε frames/
ffmpeg -framerate 30 -i frames/f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 17 archforge_film_9x16.mp4
```

Δοκιμαστικά καρέ: `node capture.js stills 720 1280 0 0 "6,12,18,24"`.
