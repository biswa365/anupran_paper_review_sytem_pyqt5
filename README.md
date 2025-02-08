# PyQt5 Expert-Paper Matching System

## Overview
This project is a GUI-based application developed using **PyQt5** and **SQLite3**, designed to facilitate the matching of experts with research papers for review. It provides functionalities for stable and greedy matching algorithms, database management, and real-time UI updates.

## Features
- **Stable Matching Algorithm**: Implements a stable matching mechanism for assigning experts to papers.
- **Greedy Selection Algorithm**: Allows for quick assignment of experts to papers based on predefined heuristics.
- **Database Management**: Uses SQLite to store and retrieve expert and paper details.
- **Multi-threading Support**: Optimizes matching operations using threading for faster execution.
- **Real-time UI Updates**: Provides interactive tables and progress tracking.

## Requirements
Ensure you have the following dependencies installed:

```bash
pip install PyQt5 numpy sqlite3
```

## Installation
1. Clone the repository:

   ```bash
   git clone https://github.com/biswa365/anupran_paper_review_sytem_pyqt5.git
   cd anupran_paper_review_sytem_pyqt5
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## File Structure
- `main.py` - Main application logic and UI control.
- `main_gui.py` - Auto-generated UI file (PyQt5).
- `mydb.db` - SQLite database containing experts and papers.
- `requirements.txt` - List of dependencies.

## Usage
1. **Load Data**: The application fetches experts and papers from `mydb.db`.
2. **Match Papers & Experts**:
   - Click `Greedy Select` to perform a fast matching.
   - Click `Stable Match` to execute the stable matching algorithm.
   - Click `Save` to commit the matches to the database.
3. **Review System**:
   - Mark papers as `Reviewed` or `Not Reviewed`.
   - Adjust expert load dynamically based on completed reviews.

## Database Schema
**Table: `expertname`**
- `expertid` (INTEGER, PRIMARY KEY)
- `name` (TEXT)
- `load` (INTEGER)
- `maxload` (INTEGER)
- `expertise1` to `expertise5` (TEXT)

**Table: `papers`**
- `paperid` (INTEGER, PRIMARY KEY)
- `title` (TEXT)
- `pages` (INTEGER)
- `expertid` (INTEGER, FOREIGN KEY)
- `status` (INTEGER, 0 = Not Reviewed, 1 = Reviewed)
- `topic1` to `topic5` (TEXT)

## Multi-threading Support
- Enable **multi-threading** for parallel matching using `self.cbMultithread.checkState() == 2`.
- Threads execute `stableMatch()` independently and merge results.

## Contributing
1. Fork the repository.
2. Create a new branch (`feature-branch`).
3. Commit your changes.
4. Push to the branch and create a pull request.

## License
None

## Contact
Author: Biswadarshi Naik.

For any issues, please create an issue in the repository or email `biswa.sipu@gmail.com`.
