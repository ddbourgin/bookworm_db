# bookworm_db
Modifications to database construction scripts. Forked from https://github.com/Bookworm-project/BookwormDB

There are 4 major "moving parts" for the bookworm:

1. *The bookworm data*
  - This is handled by the code in the [`force_align`](https://github.com/ddbourgin/force_align) repo. 
  - Briefly, this entails downloading the audio, matching it to its transcript, transcribing it phonetically, and then organizing the two transcriptions into a bookworm-readable format

2. *The bookworm database*
  - This is handled by the code in the [`bookworm_db`](https://github.com/ddbourgin/bookworm_db) repo
  - This code takes the bookworm data produced via the force_align code and organizes it into a SQL database for use with the bookworm API
  * Important pieces of code here are
    - `Makefile`                      -> High level overview of database construction
    - `bookworm/tokenizer.py`         -> Contains the regexes used for tokenizing the bookworm data
    - `bookworm/CreateDatabase.py`    -> Includes rules and SQL calls for constructing the tables in the database
    - `OneClick.py`                   -> Calls the functions in CreateDatabase during db construction

3. *The bookworm API*
  - This is handled by the code in the [`bookworm_api`](https://github.com/ddbourgin/bookworm_api) repo
  - This code is the interface between the bookworm browser/gui and the bookworm database as constructed using the code in bookworm_db
  * Important pieces of code here
    - `dbbindings.py`                 -> This is the script that receives queries from the front-end, sends them along to the API, and returns the results
    - `bookworm/general_API.py`       -> The general API for constructing database queries from 
    - `bookworm/SQLAPI.py`            -> Defines the `userqueries` class for querying the bookworm database and parsing the response

4. *The bookworm GUI*
  - This is handled by the code in the [`bookworm_gui`](https://github.com/ddbourgin/bookworm_gui) repo
  - This is the front-end for the bookworm browser. The majority of the processing is handled in bookworm_gui/static/js/a.js
  * Important pieces of code here are
    - `index.html`
    - `static/js/a.js`        -> This is where the calls to the API are constructed; handles look + feel of the interface
    - `static/options.json`   -> The config file containing the default values for the front-end as well as lookup tables for translating database names into display names 


## Workflow:
1. Construct a bookworm data zip
  - For the formatting requirements, refer to: https://bookworm-project.github.io/Docs/Requirements.html

2. Initialize a server (I usually use the AWS EC2 Ubuntu free-tier). Ensure that permissions are set to allow unrestricted access to http and https ports.

4. SSH in to the server and clone the `bookworm_db` repo into `/var/www/`

5. Rename the database to the name of your bookworm, e.g., `sudo mv bookworm_db My_BW_Name`

6. Create a directory called `files` within the renamed bookworm_db

7. Copy the `texts` and `metadata` folders in your bookworm data to the files directory.

8. Run `sudo make all` to set up 

##TODO:
1. Add code for creating pause and word:pronunciation tables to `CreateDatabase.py`
