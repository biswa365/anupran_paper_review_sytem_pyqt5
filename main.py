import sys
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import sqlite3
import numpy as np
import threading
import time
from main_gui import Ui_mainWindow

dbpath = 'mydb.db'

class ReturnableThread(threading.Thread):
    """
    A subclass of threading.Thread that allows the thread to return a result.

    Parameters:
    ----------
    target : Callable
        The function that the thread will execute. This function should return a value that 
        will be stored in `self.result` after the thread completes.
    args : tuple, optional
        Positional arguments to pass to the target function.
    kwargs : dict, optional
        Keyword arguments to pass to the target function.

    Attributes:
    ----------
    result : Any
        Stores the result of the target function after execution.
    """
    # This class is a subclass of Thread that allows the thread to return a value.
    def __init__(self, target):
        threading.Thread.__init__(self)
        self.target = target
        self.result = None
    
    def run(self) -> None:
        self.result = self.target()

class MainWindow(QtWidgets.QMainWindow, Ui_mainWindow):
    resultsReady = pyqtSignal(list, dict, str, dict, dict, int)
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.showMaximized()
        self.connection = sqlite3.connect(dbpath)
        self.setupUi(self)
        self.check_list = []
        self.paper_details = []
        self.expert_details = []
        self.free_expert_id = []
        self.free_expert_spec = []
        self.free_paper_id = []
        self.free_paper_spec = []
        self.expert_id = []
        self.expert_name = []
        self.expert_match_list = []
        self.totalScore = 0
        self.btnReviewed.setEnabled(False)
        self.btnNotReviewed.setEnabled(False)
        self.updateLoadTable()
        self.updatePaperTable()
        self.mutex = True
        
        self.resultsReady.connect(self.updateMatchTable)
        self.btnReset.clicked.connect(self.onResetClicked)
        self.btnStableMatch.clicked.connect(self.onStableMatchClicked)
        self.btnGreedySelect.clicked.connect(self.onGreedySelectClicked)
        self.btnNonGreedySelect.clicked.connect(self.onNonGreedySelectClicked)
        self.btnSave.clicked.connect(self.onSaveClicked)
        self.tableMatchOutput.cellClicked.connect(self.onMatchTableCellClicked)
        self.tablePapers.cellClicked.connect(self.onPapersTableClicked)
        self.btnReviewed.clicked.connect(self.onReviewedClicked)
        self.btnNotReviewed.clicked.connect(self.onNotReviewedClicked)
    
    def closeEvent(self, event):
        self.connection.commit()
        self.connection.close()
    
    def executeQuery(self, query, params=None, fetch_all=True, commit=False):
        """
        Executes a SQL query on the connected database.

        Parameters:
        - query (str): The SQL query to be executed.
        - params (tuple, optional): A tuple of parameters to safely pass to the SQL query. Defaults to None.
        - fetch_all (bool, optional): If True, fetches all results; if False, fetches only one result. Defaults to True.
        - commit (bool, optional): If True, commits the transaction. Defaults to False.

        Returns:
        - list or tuple: The result of the query. Returns a list of rows if `fetch_all` is True, a single row if `fetch_all` is False, or None if there was an error.

        Notes:
        - Ensures the cursor is closed after execution.
        - Recommended to use `params` for parameterized queries to prevent SQL injection.
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall() if fetch_all else cursor.fetchone()
            if commit:
                self.connection.commit()
            return result
        except sqlite3.Error as error:
            print("Error occurred -", error)
            return None
        finally:
            cursor.close()
    
    def stableMatch(self, expert: list, expert_spec: list[list], paper: list, paper_spec: list[list], thread_name: str):
        """
        Implements a stable matching algorithm to match experts with papers based on their compatibility scores.

        Parameters:
        - expert (list): A list of experts to be matched.
        - expert_spec (list): A list of specifications for each expert. Each entry corresponds to an expert in `expert`.
        - paper (list): A list of papers to be matched.
        - paper_spec (list): A list of specifications for each paper. Each entry corresponds to a paper in `paper`.
        - thread_name (str): The name of the thread, used for tracking and updating match progress in a multi-threaded environment.

        Returns:
        - tuple: A tuple containing:
            - expert_match (dict): A dictionary where each expert is mapped to a matched paper or 'free' if unmatched.
            - score_list (dict): A dictionary containing the match score for each expert, with unmatched experts having a score of 0.

        Notes:
        - The method initializes each expert and paper as "free" (unmatched) and iteratively scores pairs to find optimal matches.
        - Calls `self.matchScore()` to compute compatibility scores between an expert's specifications and a paper's specifications.
        - Calls `self.updateMatchTable()` to update the match table UI or log as progress is made.
        - Updates a progress bar (`self.pbProgress`) based on the current number of matched experts.
        - Implements a mechanism to handle situations where a new, higher score allows for rematching, ensuring each expert-paper pair is matched optimally.
        """
        # Initialize all lists and dictionaries
        expert_match = {e: 'free' for e in expert}
        paper_match = {p: 'free' for p in paper}
        score_list = {e: 0 for e in expert}
        status = {e: '' for e in expert}
        initial_score = [0 for w in range(5)]
        score_weights_list = {e: initial_score for e in expert}
        score_list['free'] = 0
        length_match_values = len(list(paper_match.values()))
        
        self.pbProgress.setMaximum(length_match_values - 1)
        progress = 0
        while 'free' in paper_match.values():
            for e in expert:
                for p in paper:
                    status = {e: '' for e in expert}
                    score, score_weights = self.matchScore(expert_spec[expert.index(e)], paper_spec[paper.index(p)])
                    if score > 0 and expert_match[e] == 'free' and paper_match[p] == 'free':
                        expert_match[e] = p
                        paper_match[p] = e
                        score_list[e] = score
                        score_weights_list[e] = score_weights
                        status[e] = 'Make-up!'
                        self.resultsReady.emit(list(expert_match.items()), score_list.copy(), thread_name, score_weights_list.copy(), status.copy(), progress)
                    elif score > score_list[e]:
                        if score > score_list[paper_match[p]]:
                            prev_e_match = expert_match[e]
                            prev_p_match = paper_match[p]
                            expert_match[e] = p
                            paper_match[p] = e
                            score_list[e] = score
                            score_weights_list[e] = score_weights
                            status[e] = 'Make-up!'
                            if prev_e_match != 'free': 
                                paper_match[prev_e_match] = 'free'
                            if prev_p_match != 'free': 
                                score_list[prev_p_match] = 0
                                score_weights_list[prev_p_match] = initial_score
                                status[prev_p_match] = 'Break-up!'
                                expert_match[prev_p_match] = 'free'
                            self.resultsReady.emit(list(expert_match.items()).copy(), score_list.copy(), thread_name, score_weights_list.copy(), status.copy(), progress)
                    progress = length_match_values - list(expert_match.values()).count('free')
        return expert_match, score_list
    
    def setColortoRow(self, table: QTableWidget, rowIndex: int, color: QColor, alpha=None):
        """
        Sets the background color for all cells in a specific row of a QTableWidget.
        
        Parameters:
        - table: QTableWidget, the table in which to set the row color.
        - rowIndex: int, the index of the row to color.
        - color: QColor, the base color to apply.
        - alpha: int or list of int (optional), transparency level(s) for the color.
                - If an integer, applies the same alpha to all cells in the row.
                - If a list, each value corresponds to the alpha for each column in the row.
        """
        if not (0 <= rowIndex < table.rowCount()):
            raise ValueError("rowIndex out of range")
        for colIndex in range(table.columnCount()):
            item = table.item(rowIndex, colIndex)
            if item is None:
                item = QTableWidgetItem()  # Create item if it doesn't exist
                table.setItem(rowIndex, colIndex, item)
            cell_color = QColor(color)  # Create a copy of color to avoid altering the original
            # Set alpha based on provided argument
            if alpha is not None:
                if isinstance(alpha, int):
                    cell_color.setAlpha(alpha)
                elif isinstance(alpha, list) and colIndex < len(alpha):
                    cell_color.setAlpha(alpha[colIndex])
            item.setBackground(cell_color)
    
    def randomLightColor(self):
        """
        Generates a random light QColor with semi-transparency.

        This method:
        - Randomly generates RGB values within a higher range (128 to 255) to ensure the color is light.
        - Sets a fixed alpha (transparency) value of 100 for a consistent semi-transparent appearance.

        Returns:
        - QColor: A QColor object with a light random color and semi-transparency.
        """
        # Generate RGB values in the range of 128 to 255 for a lighter color
        c = list(np.random.choice(range(128, 256), size=3))
        color = QColor(c[0], c[1], c[2], 100)  # Set alpha to 100 for semi-transparency
        return color
    
    def updateMatchTable(self, match_list: list, match_score: dict, thread_name: str, score_weights_list: dict, status: dict, progress: int):
        """
        Updates the table displaying match results by inserting rows for each match and applying colors.

        This method:
        - Inserts a new row in the `tableMatchOutput` for each item in `match_list`, displaying information about matched pairs.
        - Populates each cell in the new row with details, including match IDs, scores, thread name, and weighted scores.
        - Sets a light background color for each row, with alpha transparency inversely scaled by weight values, to make higher weights darker.
        - Adjusts column widths to fit content after updates.

        Parameters:
        - match_list (list of tuples): List of pairs (expert, paper) to display.
        - match_score (dict): Dictionary of match scores, with expert IDs as keys.
        - thread_name (str): Name of the thread handling the match.
        - score_weights_list (list of lists): Each sublist contains score weights for a specific expert.

        Returns:
        - None
        """
        self.pbProgress.setValue(progress)
        color = self.randomLightColor()  # Generate a random light color for row backgrounds
        
        for row in range(len(match_list)):
            self.tableMatchOutput.insertRow(0)  # Insert a new row at the top
            self.tableMatchOutput.setItem(0, 0, QTableWidgetItem(str(match_list[row][0])))  # Expert ID
            self.tableMatchOutput.setItem(0, 1, QTableWidgetItem('==>'))  # Arrow symbol
            self.tableMatchOutput.setItem(0, 2, QTableWidgetItem(str(match_list[row][1])))  # Paper ID
            self.tableMatchOutput.setItem(0, 3, QTableWidgetItem(str(match_score[int(match_list[row][0])])))  # Match score
            self.tableMatchOutput.setItem(0, 4, QTableWidgetItem(thread_name))  # Thread name
            self.tableMatchOutput.setItem(0, 10, QTableWidgetItem(str(status[int(match_list[row][0])])))
            
            # Display individual score weights in columns 5 to 9
            for col in range(5, 10):
                weight = score_weights_list[int(match_list[row][0])][col - 5]
                self.tableMatchOutput.setItem(0, col, QTableWidgetItem(str(weight)))
            
            # Scale alpha based on weight values: lighter for low weight, darker for high weight
            alpha = [70, 70, 70, 70, 70] + [
                int((weight / 25) * 200) for weight in score_weights_list[int(match_list[row][0])]
            ] + [70]
            # Alpha values now range from 100 (lightest) to 30 (darkest) based on weight scaling            
            self.setColortoRow(self.tableMatchOutput, 0, color, alpha)
        self.tableMatchOutput.resizeColumnsToContents()  # Adjust column widths to fit content
        
    def updateLoadTable(self):
        """
        Updates `tableLoadTable` with data from the `expertname` table, applying
        color to rows based on a percentage value.

        Retrieves data from the database, clears existing rows, and sets new rows
        with `expert_details`. Each row's background color is set based on the
        percentage value in column 2.

        Attributes:
        ----------
        expert_id : list
            Stores expert IDs extracted from the database.
        expert_name : list
            Stores expert names extracted from the database.
        """
        # Clear table and local lists
        self.tableLoadTable.setRowCount(0)
        expert_details = np.array(self.executeQuery('SELECT * FROM expertname'))
        self.expert_id.clear()
        self.expert_name.clear()
        
        # Populate table with new data
        for row, data in enumerate(expert_details):
            self.expert_id.append(int(data[0]))
            self.expert_name.append(str(data[1]))
            self.tableLoadTable.insertRow(row)
            
            for col in range(9):  # Assuming there are 9 columns
                item = QTableWidgetItem(str(data[col]))
                self.tableLoadTable.setItem(row, col, item)
            
            # Apply color based on percentage value in column 2
            percent = int(float(data[2]))
            color = QColor(255, 0, 0, percent)
            self.setColortoRow(self.tableLoadTable, row, color)
        
        self.tableLoadTable.resizeColumnsToContents()
    
    def updatePaperTable(self):
        """
        Updates the `tablePapers` with data from the `papers` table.

        Clears existing rows in the table and populates it with new data retrieved 
        from the database. Each row displays information about papers, including 
        assignment and review status. Rows are color-coded based on the review status.

        Attributes:
        ----------
        paper_details : np.ndarray
            An array containing the details of the papers retrieved from the database.
        """
        # Clear the table and reset paper details
        self.tablePapers.setRowCount(0)
        paper_details = np.array(self.executeQuery('SELECT * FROM papers'))
        self.paper_details = paper_details

        # Populate table with paper details
        for row, data in enumerate(paper_details):
            self.tablePapers.insertRow(row)

            # Set items in each column
            self.tablePapers.setItem(row, 0, QTableWidgetItem(str(data[0])))
            self.tablePapers.setItem(row, 1, QTableWidgetItem('Not Assigned' if int(data[3]) == -1 
                                                                else self.expert_name[self.expert_id.index(int(data[3]))]))
            self.tablePapers.setItem(row, 2, QTableWidgetItem('Not Reviewed' if int(data[4]) == 0 else 'Reviewed'))
            self.tablePapers.setItem(row, 3, QTableWidgetItem(str(data[2])))
            self.tablePapers.setItem(row, 4, QTableWidgetItem(str(data[1])))
            self.tablePapers.setItem(row, 5, QTableWidgetItem(str(data[5])))
            self.tablePapers.setItem(row, 6, QTableWidgetItem(str(data[6])))
            self.tablePapers.setItem(row, 7, QTableWidgetItem(str(data[7])))
            self.tablePapers.setItem(row, 8, QTableWidgetItem(str(data[8])))
            self.tablePapers.setItem(row, 9, QTableWidgetItem(str(data[9])))

            # Apply color if the paper has been reviewed
            if int(data[4]) != 0:
                color = QColor(0, 255, 0, 100)
                self.setColortoRow(self.tablePapers, row, color)

        # Resize columns to fit content
        self.tablePapers.resizeColumnsToContents()
    
    def matchScore(self, list1: list, list2: list):
        """
        Calculates a compatibility score between two lists of preferences or specifications.

        Parameters:
        - list1 (list): The first list of preferences/specifications, typically representing an expert's preferences.
        - list2 (list): The second list of preferences/specifications, typically representing a paper's preferences.

        Returns:
        - int: The computed compatibility score. Higher scores indicate a better match between the two lists.

        Calculation:
        - Each item in `list1` is assigned a score based on its position, with earlier items receiving higher scores.
        - For each item in `list1`, the method checks for its position in `list2`:
            - If found, both positions are converted to scores, with earlier positions having higher weights.
            - These positional scores are multiplied and added to the total compatibility score.
            - If an item in `list1` is not found in `list2`, it contributes a score of 0.

        Notes:
        - The method dynamically determines the scoring range based on the length of `list1`, so it adapts to lists of varying lengths.
        - This function is useful for ranking and matching based on overlapping preferences or specifications between two entities.
        """
        score = 0
        scote_list = []
        max_score = len(list1)  # Dynamically set the maximum score based on the length of list1       
        for index, item in enumerate(list1):
            score1 = max_score - index  # Score for the current item in list1
            try:
                score2 = max_score - list2.index(item)  # Score based on position of item in list2
            except ValueError:
                score2 = 0  # Item not found in list2          
            score += score1 * score2
            scote_list.append(score1 * score2)
        return score, scote_list
    
    def onResetClicked(self):
        """
        Resets the application's state to its initial configuration.

        Clears various lists and attributes related to papers and experts,
        updates the database to reset loads and statuses, and refreshes 
        the user interface components, including tables and progress bars.
        Displays a message box to inform the user that the reset is complete.
        """
        # Clear lists and reset attributes
        self.check_list = []
        self.paper_details = []
        self.expert_details = []
        self.free_expert_id = []
        self.free_expert_spec = []
        self.free_paper_id = []
        self.free_paper_spec = []
        self.expert_id = []
        self.expert_name = []
        self.expert_match_list = []
        self.totalScore = 0
        
        # Disable buttons and reset label
        self.btnReviewed.setEnabled(False)
        self.btnNotReviewed.setEnabled(False)
        self.lblTotalScore.setText('Total Score: ')
        
        # Update the database to reset values
        self.executeQuery('UPDATE expertname SET load = 0')
        self.executeQuery('UPDATE papers SET expertid = -1, status = 0')
        
        # Clear tables and reset progress
        self.tableLoadTable.setRowCount(0)
        self.tablePapers.setRowCount(0)
        self.tableFreeExpert.setRowCount(0)
        self.tableFreePaper.setRowCount(0)
        self.tableMatchOutput.setRowCount(0)
        
        # Refresh tables with updated data
        self.updateLoadTable()
        self.updatePaperTable()
        
        # Reset progress bar
        self.pbProgress.setValue(0)
        
        # Inform the user that the reset is complete
        QMessageBox.information(self, "Information", 'Reset done.')
    
    def updateSelectTable(self, free_paper_list, free_expert_list):
        """
        Updates the free expert and paper tables with data from the provided lists.

        This method fetches the expertise data from the database and populates 
        the `tableFreeExpert` and `tableFreePaper` tables with the corresponding 
        free experts and papers. The number of entries displayed is determined 
        by the minimum length of the free expert IDs, free paper IDs, and the 
        value of the batch size spinner.

        Parameters:
        ----------
        free_paper_list : list
            A list of free papers, where each paper is represented as a tuple.
        free_expert_list : list
            A list of free experts, where each expert is represented as a tuple.
        """
        expertise_list = self.executeQuery('SELECT * FROM expertise')
        expertise = {e[1]: e[0] for e in expertise_list}
        length = min(len(self.free_expert_id), len(self.free_paper_id), self.spinBatcSize.value())
        self.tableFreeExpert.setRowCount(0)
        for row in range(length):
            self.tableFreeExpert.setRowCount(self.tableFreeExpert.rowCount() + 1)
            self.tableFreeExpert.setItem(row, 0, QTableWidgetItem(str(free_expert_list[row][0])))
            self.tableFreeExpert.setItem(row, 1, QTableWidgetItem(str(expertise[free_expert_list[row][4]])))
            self.tableFreeExpert.setItem(row, 2, QTableWidgetItem(str(expertise[free_expert_list[row][5]])))
            self.tableFreeExpert.setItem(row, 3, QTableWidgetItem(str(expertise[free_expert_list[row][6]])))
            self.tableFreeExpert.setItem(row, 4, QTableWidgetItem(str(expertise[free_expert_list[row][7]])))
            self.tableFreeExpert.setItem(row, 5, QTableWidgetItem(str(expertise[free_expert_list[row][8]])))
            self.tableFreeExpert.setItem(row, 6, QTableWidgetItem(str(free_expert_list[row][1])))
        self.tableFreeExpert.resizeColumnsToContents()
        self.tableFreePaper.setRowCount(0)
        for row in range(length):
            self.tableFreePaper.setRowCount(self.tableFreePaper.rowCount() + 1)
            self.tableFreePaper.setItem(row, 0, QTableWidgetItem(str(free_paper_list[row][0])))
            self.tableFreePaper.setItem(row, 1, QTableWidgetItem(str(expertise[free_paper_list[row][5]])))
            self.tableFreePaper.setItem(row, 2, QTableWidgetItem(str(expertise[free_paper_list[row][6]])))
            self.tableFreePaper.setItem(row, 3, QTableWidgetItem(str(expertise[free_paper_list[row][7]])))
            self.tableFreePaper.setItem(row, 4, QTableWidgetItem(str(expertise[free_paper_list[row][8]])))
            self.tableFreePaper.setItem(row, 5, QTableWidgetItem(str(expertise[free_paper_list[row][9]])))
            self.tableFreePaper.setItem(row, 6, QTableWidgetItem(str(free_paper_list[row][1])))
        self.tableFreePaper.resizeColumnsToContents()
        
    def onGreedySelectClicked(self):
        """
        Handles the greedy selection of papers and experts based on availability and load constraints.

        This method:
        - Retrieves a list of papers without assigned experts (`expertid == -1`) and resets the
        `free_paper_id` and `free_paper_spec` lists with the resulting data.
        - Retrieves a list of available experts with load less than 80, ordered by ascending load.
        Resets `free_expert_id` and `free_expert_spec` lists with the resulting data.
        - Updates the selection table to reflect the current state of free papers and available experts.

        Notes:
        - Calls `executeQuery()` for database operations and `updateSelectTable()` to update the table display.
        - Assumes the `free_paper_id`, `free_paper_spec`, `free_expert_id`, and `free_expert_spec` lists exist.

        Returns:
        - None
        """
        
        # Retrieve and process list of unassigned papers
        free_paper_list = self.executeQuery('SELECT * FROM papers WHERE expertid = -1')
        self.free_paper_id.clear()
        self.free_paper_spec.clear()
        if free_paper_list:
            self.free_paper_id = [int(row[0]) for row in free_paper_list]
            self.free_paper_spec = [[row[5], row[6], row[7], row[8], row[9]] for row in free_paper_list]

        # Retrieve and process list of available experts
        free_expert_list = self.executeQuery('SELECT * FROM expertname WHERE load < 80 ORDER BY load ASC')
        self.free_expert_id.clear()
        self.free_expert_spec.clear()
        if free_expert_list:
            self.free_expert_id = [int(row[0]) for row in free_expert_list]
            self.free_expert_spec = [[row[4], row[5], row[6], row[7], row[8]] for row in free_expert_list]

        # Update selection table to reflect the new lists
        self.updateSelectTable(free_paper_list, free_expert_list)
    
    def onNonGreedySelectClicked(self):
        """
        Handles non-greedy selection by finding available experts for unassigned papers based on expertise matches.

        This method:
        - Retrieves unassigned papers (where `expertid == -1`).
        - For each paper, searches for suitable experts within specified depth limits for both experts and paper requirements.
        - Populates `free_expert_id` and `free_expert_spec` with unique experts and associates them with compatible papers.
        - Updates the selection table with the selected papers and experts.

        Returns:
        - None
        """
        
        # Retrieve unassigned papers
        free_paper = self.executeQuery('SELECT * FROM papers WHERE expertid = -1')
        free_paper_spec = [[row[5], row[6], row[7], row[8], row[9]] for row in free_paper] if free_paper else []
        
        # Clear current expert and paper lists
        self.free_expert_id.clear()
        self.free_expert_spec.clear()
        self.free_paper_id.clear()
        self.free_paper_spec.clear()
        free_expert_list = []
        free_paper_list = []
        
        # Loop through each paper to find a suitable expert match
        for paper_index, paper_spec in enumerate(free_paper_spec):
            found_expert = False  # Track if a match is found for current paper
            # Search for experts with matching expertise within depth limits
            for e_depth in range(self.spinExpertDepth.value()):
                for p_depth in range(self.spinPaperDepth.value()):
                    query = f'''
                        SELECT * FROM expertname 
                        WHERE load < 100 AND expertise{e_depth + 1} = "{paper_spec[p_depth]}"
                        ORDER BY load ASC
                    '''
                    free_expert = self.executeQuery(query, fetch_all=False)
                    
                    if free_expert and int(free_expert[0]) not in self.free_expert_id:
                        # Add the expert and associated paper details if the expert is unique
                        self.free_expert_id.append(int(free_expert[0]))
                        self.free_expert_spec.append([free_expert[4], free_expert[5], free_expert[6], free_expert[7], free_expert[8]])
                        free_expert_list.append(free_expert)
                        
                        paper = free_paper[paper_index]
                        self.free_paper_id.append(int(paper[0]))
                        self.free_paper_spec.append([paper[5], paper[6], paper[7], paper[8], paper[9]])
                        free_paper_list.append(paper)
                        
                        found_expert = True  # Match found, move to the next paper
                        break
                
                if found_expert:
                    break
        # Update selection table with the results
        self.updateSelectTable(free_paper_list, free_expert_list)
            
    def onStableMatchClicked(self):
        """
        Initiates the stable matching process between free experts and papers.

        This method checks if there are available experts and papers. If so, it 
        prepares to perform the stable matching either in a single-threaded or 
        multi-threaded manner based on user selection. The results of the matching 
        process are then stored for further processing.

        The matching is performed using the `stableMatch` method, and the results 
        are combined if multi-threading is enabled.

        Raises:
        ------
        Exception: If no experts or papers are available for matching.
        """        
        if len(self.free_expert_id) > 0 and len(self.free_paper_id) > 0:
            self.tableMatchOutput.setRowCount(0)
            length = min(len(self.free_expert_id), len(self.free_paper_id), self.spinBatcSize.value())
            mid = length//2 if self.cbMultithread.checkState() == 2 else length
            newThread1 = ReturnableThread(target=lambda: self.stableMatch(self.free_expert_id[0:mid], self.free_expert_spec[0:mid], self.free_paper_id[0:mid], self.free_paper_spec[0:mid], 'thread1'))
            newThread2 = ReturnableThread(target=lambda: self.stableMatch(self.free_expert_id[mid:length], self.free_expert_spec[mid:length], self.free_paper_id[mid:length], self.free_paper_spec[mid:length], 'thread2'))
            newThread1.start()
            if self.cbMultithread.checkState() == 2:
                newThread2.start()
            newThread1.join()
            if self.cbMultithread.checkState() == 2:
                newThread2.join()
            expert_match_list, match_score = newThread1.result
            if self.cbMultithread.checkState() == 2:
                expert_match_list2, match_score2 = newThread2.result
                expert_match_list.update(expert_match_list2)
                match_score.update(match_score2)
            self.expert_match_list = list(expert_match_list.items())
            self.match_score = match_score

    def onSaveClicked(self):
        """
        Saves the current expert-paper matching by updating the database.

        This method checks if the current expert-paper matching differs from the
        previously saved matches. If they are different, it updates the load for 
        each expert and assigns the corresponding expert to each paper. Progress 
        is reflected in a progress bar, and the total score is updated accordingly.

        Updates the following:
        - Expert loads based on the number of pages assigned to them.
        - Paper assignments for each expert.

        Raises:
        ------
        Exception: If an error occurs while executing database queries.
        """
        if self.check_list != self.expert_match_list:
            self.check_list = self.expert_match_list.copy()
            self.pbProgress.setMaximum(len(self.expert_match_list))
            for idx, (expert_id, paper_id) in enumerate(self.expert_match_list):
                load, max_load = self.executeQuery(f'SELECT load, maxload FROM expertname WHERE expertid={expert_id}', fetch_all=False)
                pages, _ = self.executeQuery(f'SELECT pages, paperid FROM papers WHERE paperid={paper_id}', fetch_all=False)
                revised_load = min(100, round(load + (pages / max_load) * 100, 2))
                if revised_load != load:
                    self.executeQuery(f'UPDATE expertname SET load={revised_load} WHERE expertid={expert_id}')
                self.executeQuery(f'UPDATE papers SET expertid={expert_id} WHERE paperid={paper_id}')
                self.pbProgress.setValue(idx + 1)
            
            self.totalScore += sum(map(int, list(self.match_score.values())))
            self.lblTotalScore.setText(f'Total Score: {self.totalScore}')
            self.updateLoadTable()
            self.updatePaperTable()
    
    def onMatchTableCellClicked(self, row, _ ):
        """
        Handles the event when a cell in the match table is clicked.

        This method retrieves the expert ID and paper ID from the selected 
        row in the match output table. It then selects the corresponding 
        expert and paper in their respective tables, allowing the user to 
        easily view their details.

        Parameters:
        ----------
        row : int
            The index of the clicked row in the match output table.
        _ : Any
            The index of the clicked column (unused).
        """
        expert_id = self.tableMatchOutput.item(row, 0).text()
        paper_id = self.tableMatchOutput.item(row, 2).text()
        for rowIndex in range(self.tableFreePaper.rowCount()):
            if self.tableFreePaper.item(rowIndex, 0).text() == paper_id:
                item = self.tableFreePaper.item(rowIndex, 0)
                self.tableFreePaper.setCurrentItem(item)
        for rowIndex in range(self.tableFreeExpert.rowCount()):
            if self.tableFreeExpert.item(rowIndex, 0).text() == expert_id:
                item = self.tableFreeExpert.item(rowIndex, 0)  
                self.tableFreeExpert.setCurrentItem(item)
    
    def onPapersTableClicked(self, row, _ ):
        """
        Handles the event when a row in the papers table is clicked.

        This method retrieves the selected expert, paper ID, and paper status 
        from the clicked row. It then enables or disables the review buttons 
        based on the paper's review status and whether an expert is assigned.

        Parameters:
        ----------
        row : int
            The index of the clicked row in the papers table.
        _ : Any
            The index of the clicked column (unused).
        """
        self.selected_expert = self.tablePapers.item(row, 1).text()
        self.selected_paper_id = self.tablePapers.item(row, 0).text()
        self.selected_paper_status = self.tablePapers.item(row, 2).text()
        if self.expert_name != 'Not Assigned' and self.selected_paper_status == 'Not Reviewed':
            self.btnReviewed.setEnabled(True)
            self.btnNotReviewed.setEnabled(False)
        if self.expert_name != 'Not Assigned' and self.selected_paper_status == 'Reviewed':
            self.btnReviewed.setEnabled(False)
            self.btnNotReviewed.setEnabled(True)
    
    def onReviewedClicked(self):
        if self.selected_expert != 'Not Assigned' and self.selected_paper_status == 'Not Reviewed':
            expert_id = str(self.expert_id[self.expert_name.index(self.selected_expert)])
            paper_id = self.selected_paper_id
            load, max_load = self.executeQuery('select load, maxload from expertname where expertid=' + expert_id)[0]
            pages, = self.executeQuery('select pages from papers where paperid=' + paper_id)[0]
            revised_load = round((max_load * load / 100 - int(pages)) / max_load * 100, 2)
            revised_load = 0 if revised_load < 0 else revised_load
            self.executeQuery('update expertname set load=' + str(revised_load) + ' where expertid=' + expert_id)
            self.executeQuery('update papers set status=1 where paperid='+ paper_id)
            self.updatePaperTable()
            self.updateLoadTable()
    
    def onNotReviewedClicked(self):
        if self.expert_name != 'Not Assigned' and self.selected_paper_status == 'Reviewed':
            expert_id = str(self.expert_id[self.expert_name.index(self.selected_expert)])
            paper_id = self.selected_paper_id
            load, max_load = self.executeQuery('select load, maxload from expertname where expertid=' + expert_id)[0]
            pages, = self.executeQuery('select pages from papers where paperid=' + paper_id)[0]
            revised_load = round((max_load * load / 100 + int(pages)) / max_load * 100, 2)
            revised_load = 100 if revised_load > 100 else revised_load
            self.executeQuery('update expertname set load=' + str(revised_load) + ' where expertid=' + expert_id)
            self.executeQuery('update papers set status=0 where paperid='+ paper_id)
            self.updatePaperTable()
            self.updateLoadTable()

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()