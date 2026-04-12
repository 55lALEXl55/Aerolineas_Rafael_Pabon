.PHONY: up down seed logs reset build status health

up:
	docker-compose up --build -d

down:
	docker-compose down

seed:
	python database/seed/load_dataset.py

logs:
	docker-compose logs -f

reset:
	docker-compose down -v && docker-compose up --build -d

build:
	docker-compose build

status:
	docker-compose ps

health:
	@echo "--- ms-flights ---"
	curl -s http://localhost:8001/health | python -m json.tool
	@echo "--- ms-bookings ---"
	curl -s http://localhost:8002/health | python -m json.tool
	@echo "--- ms-routes ---"
	curl -s http://localhost:8003/health | python -m json.tool
	@echo "--- ms-sync ---"
	curl -s http://localhost:8004/health | python -m json.tool
	@echo "--- ms-tickets ---"
	curl -s http://localhost:8005/health | python -m json.tool
	@echo "--- ms-dashboard ---"
	curl -s http://localhost:8006/health | python -m json.tool
