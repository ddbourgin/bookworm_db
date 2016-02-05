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
    - `bookworm/general_API.py`       -> The general API for organizing and parsing database queries. Makes use of the `userquery` class in `SQLAPI.py` to actually query the database.
    - `bookworm/SQLAPI.py`            -> Defines the `userqueries` class for querying the bookworm database and parsing the response

4. *The bookworm GUI*
  - This is handled by the code in the [`bookworm_gui`](https://github.com/ddbourgin/bookworm_gui) repo
  - This is the front-end for the bookworm browser. The majority of the processing is handled in `bookworm_gui/static/js/a.js`
  * Important pieces of code here are
    - `index.html`
    - `static/js/a.js`        -> This is where the calls to the API are constructed; handles look + feel of the interface, as well as query highlighting and phoneme vs. word database selection (for now - this should be moved to server-side eventually).
    - `static/options.json`   -> The config file containing the default values for the front-end, as well as lookup tables for translating database ids into display names.


## Workflow:
1. Construct a bookworm data zip
  - For the formatting requirements, refer to: https://bookworm-project.github.io/Docs/Requirements.html

2. Initialize a server (I usually use the AWS EC2 Ubuntu free-tier). Ensure that permissions are set to allow unrestricted access to http and https ports. If the bookworm is large, make sure to allocate an appropriate swapfile to avoid segfaults during database construction.

3. SSH in to the server and clone the [`bookworm_db`](https://github.com/ddbourgin/bookworm_db) repo into `/var/www/`:
  ```shell
  sudo apt-get install git #if you're using ubuntu
  cd /var/www/
  sudo git clone https://github.com/ddbourgin/bookworm_db.git
  ```
4. Make a directory `files` in `bookworm_db` and rename the `bookworm_db` directory to your bookworm database name. For example, if your bookworm DB is named `My_BW_DB_Name`, you would run 
  ```shell
  sudo mkdir /var/www/bookworm_db/files
  sudo mv /var/www/bookworm_db /var/www/My_BW_DB_Name
  ```

5. Run the script `deploy_bw.sh` in the renamed database directory. This will install the necessary bookworm dependencies and set up the MySQL server/config files for bookworm access.
  ```shell
  sudo sh My_BW_DB_Name/deploy_bw.sh
  ```

6. From the `/var/www/` directory, download the zip file containing the bookworm data you created in step 1. I typically upload the file to dropbox and use `wget` to download:
  ```shell
  cd /var/www/
  sudo wget Link_to_Bookworm_Data_Zip
  sudo unzip *.zip
  sudo rm *.zip
  ```
7. Copy the `texts` and `metadata` folders in your unzipped `Bookworm_Data_Folder` to the files directory. 
  - We assume here that your data folder is organized as
  ```
  Bookworm_Data_Folder/
    | -- texts/
    |  | input.txt
    | -- metadata/
    |  | jsoncatalog.txt
    |  | field_descriptions.json
  ```
  - If this is so, then you can simply run the following from the `/var/www/` directory
  ```shell
  sudo mv Bookworm_Data_Folder/files My_BW_DB_Name/tests/
  sudo mv Bookworm_Data_Folder/metadata My_BW_DB_Name/metadata/
  sudo rm -rf Bookworm_Data_Folder
  ```
8. To actually construct the database
```shell
cd /var/www/My_BW_DB_Name/
sudo make all
```
9. Follow the on-screen instructions. If all has gone well, this will result in a completed Bookworm database

##TODO:
1. Add code for creating pause and word:pronunciation tables to `CreateDatabase.py`
