# GhostBot NSFW - Starter Pack

Base structure de test avec images, queue, cookies, et scripts modulaires.
ghostbot/
├── config/
│ ├── settings.yaml ← Fréquences, log, plateformes
│ └── accounts.yaml ← Infos compte/cookies/IP/email
├── cookies/ ← Emplacement cookies (à créer via script)
├── data/
│ ├── images_fleurs/ ← Ajoute ici tes images test
│ ├── images_nsfw/ ← Vide pour l’instant
│ └── queue.csv ← File d’attente avec 1 post "fleur"
├── logs/
│ ├── posted.sqlite ← Base anti-doublon
│ └── ghostbot.log ← (sera généré)
├── reddit/ ← (à compléter plus tard)
├── tumblr/
│ └── post_photo_selenium.py ← Script placeholder
├── x/ ← (à compléter plus tard)
├── utils/
│ ├── driver.py ← À venir
│ ├── logger.py ← Logger prêt à l’emploi
│ └── db.py ← DB SQLite fonctionnelle
├── scheduler/
│ └── run_cycle.py ← Script principal de publication
├── scripts/
│ └── save_cookies.py ← Script pour login manuel & cookies
├── README.md
