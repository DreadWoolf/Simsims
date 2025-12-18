# SimSims – a school project to simulate a small population

SimSims is a Python-based simulation of a small settlement where workers, food, and products flow through an adaptive network of places and transitions.  
The project was developed as part of a course assignment with focus on object-oriented design, simulation systems, and software architecture.

---

## Overview

The simulation models a small society evolving day by day. Workers consume food, produce goods, rest, reproduce, and may die due to accidents or lack of resources.  
The simulation continues until the population collapses or another termination condition is met.

The system is inspired by Petri-net–like models and emphasizes modularity, extensibility, and correctness.

---

## Core Concepts

### Resources
- **Worker** – has longevity, can reproduce or die
- **Food** – affects worker longevity based on quality
- **Product** – consumed for housing and reproduction

### Places (Abstract Data Types)
- **Barack** – queue (FIFO), stores workers
- **Barn** – queue (FIFO), stores food
- **Warehouse** – stack (LIFO), stores products

### Transitions (Multithreaded)
- **Factory** – produces products, includes accident risk
- **Fields** – produces food
- **Dining** – consumes food to affect worker longevity
- **Home** – increases longevity or creates new workers

Each transition runs as its own thread and is coordinated by a central world controller.

---

## Key Features

- Multithreaded simulation using Python threading and event-based control
- Clear inheritance hierarchy with abstract base classes for resources, places, and transitions
- Adaptive network that dynamically adds or removes places and transitions based on system state
- Analytics system with persistent storage using SQLite
- Export of simulation data to Excel and visualization via matplotlib
- Abstract data types implemented according to specification (queue and stack)

---

## Analytics

Simulation data is logged per day, tracking:
- Number of workers
- Amount of food
- Amount of products

Data is:
- Stored in an SQLite database
- Exportable to Excel (`.xlsx`)
- Visualized as graphs (`.png`)

All analytics functionality is implemented in `simsims_analytics.py`.

---

## How to Run

### Requirements
- Python 3.10 or later
- Required libraries:
  - sqlite3
  - pandas
  - openpyxl
  - matplotlib

### Run the simulation
```bash
python simsims.py
```
Simulation parameters can be adjusted in the `__main__` section:

```python
STARTING_SETTLEMENT = 1000
STARTING_RESOURCES = 1000
SLEEP_TIME = 0
```
