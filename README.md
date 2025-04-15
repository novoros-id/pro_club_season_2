# pro_club_season_2

Клуб ПРОгрессивных разработчиков Сезон 2.0


# Клонируем
!git clone https://github.com/novoros-id/pro_club_season_2.git
%cd my_project

# Переключаемся на ветку (или создаём её)
!git checkout -b dev-branch     # создать и перейти
# или
!git checkout dev-branch        # если уже существует

# Указываем имя и email один раз
!git config --global user.email "your@email.com"
!git config --global user.name "Your Name"

# Добавляем, коммитим и пушим
!git add .
!git commit -m "Add feature or fix bug"
!git push https://github.com/novoros-id/pro_club_season_2.git dev-branch

# Установка зависимостей
!pip install -r requirements.txt
