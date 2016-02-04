#!/bin/bash
# be sure to run this script with sudo!
# Manual changes needed:
#   1. For remote access to database via, e.g., SequelPro, edit /etc/mysql/my.cnf: change the bind-address to 0.0.0.0
#      Also ensure that permissions for the database are set to allow the user to have remote access via ssh
#   2. Add a user www-data to [client] in /etc/mysql/my.cnf


echo
echo "Set up the basics"
echo

sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get dist-upgrade -y
sudo apt-get install -y gcc
sudo apt-get install -y build-essential python-dev libmysqlclient-dev git
sudo apt-get install -y parallel
sudo apt-get install -y unzip

#
echo
echo "Setting up a LAMP server on EC2"
echo

sudo apt-get install -y lamp-server^
sudo mysql_secure_installation

#
echo
echo "Install Python and Extensions"
echo

sudo apt-get install -y python-dev
sudo apt-get install -y python-pip
sudo pip install regex
sudo pip install nltk
sudo pip install numpy
sudo pip install mysql-python
sudo pip install python-dateutil
sudo pip install pandas

#
echo
echo "Setting up MySQL User Accounts"
echo
echo "Type a name for a MySQL User with all writing privileges, then hit [Enter]:"
read keeper

pass_not_set=true
while [ $pass_not_set == true ]; do
  echo
  echo "Type a password for [$keeper], then hit [Enter]:"
  read -s keeperpass
  echo
  echo "Retype the password for [$keeper], then hit [Enter]:"
  read -s keeperpass2
  echo
  if [ $keeperpass != $keeperpass2 ]
    then
      echo "The passwords typed were not the same."
  fi
  if [ $keeperpass == $keeperpass2 ]
    then
      pass_not_set=false
  fi
done


echo
echo "Type a name for a MySQL User with read only privileges, then hit [Enter]:"
read reader

pass_not_set=true
while [ $pass_not_set == true ]; do
  echo
  echo "Type a password for [$reader], then hit [Enter]:"
  read -s readerpass
  echo
  echo "Retype the password for [$reader], then hit [Enter]:"
  read -s readerpass2
  echo
  if [ $readerpass != $readerpass2 ]
    then
      echo "The passwords typed were not the same."
  fi
  if [ $readerpass == $readerpass2 ]
    then
      pass_not_set=false
  fi
done

echo
echo "Log into MySQL with your original root password:"

mysql -u root -p --execute="CREATE USER '$keeper'@'localhost' IDENTIFIED BY '$keeperpass'; \
  GRANT ALL PRIVILEGES ON *.* TO '$keeper'@'localhost' WITH GRANT OPTION; \
  CREATE USER '$keeper'@'%' IDENTIFIED BY '$keeperpass'; \
  GRANT ALL PRIVILEGES ON *.* TO '$keeper'@'%' WITH GRANT OPTION; \
  CREATE USER 'admin'@'localhost'; \
  GRANT RELOAD,PROCESS ON *.* TO 'admin'@'localhost'; \
  CREATE USER '$reader'@'localhost' IDENTIFIED BY '$readerpass'; \
  GRANT SELECT ON *.* TO '$reader'@'localhost' WITH GRANT OPTION; \
  CREATE USER '$reader'@'%' IDENTIFIED BY '$readerpass'; \
  GRANT SELECT ON *.* TO '$reader'@'%' WITH GRANT OPTION;"


#
echo
echo "Now to create the MySQL .my.cnf file"
echo



# ****************************************************


cd ~
echo " " >> .my.cnf
echo "#" >> .my.cnf
echo "# The MySQL Database Server Configuration File" >> .my.cnf
echo "#" >> .my.cnf
echo " " >> .my.cnf
echo "[client]" >> .my.cnf
echo "user = $keeper" >> .my.cnf
echo "password = $keeperpass" >> .my.cnf
echo " " >> .my.cnf

echo "Enter the name for your bookworm database and press [Enter]:"
read bookw

echo
echo "Cloning bookworm database"
echo
cd /var/www/ && git clone https://github.com/ddbourgin/bookworm_db.git 
cd ./bookworm_db && mkdir files
cd ../ && mv bookworm_db "$bookw"
#cd /var/www/ && git clone https://github.com/Bookworm-project/BookwormDB.git
#cd ./BookwormDB && git checkout tags/v0.3-alpha && mkdir files

echo
echo "Cloning bookworm API"
echo
cd /usr/lib/cgi-bin && git clone https://github.com/ddbourgin/bookworm_api.git
mv ./bookworm_api/* ./ && rm -rf ./bookworm_api
chmod -R 755 /usr/lib/cgi-bin && chown -R root.root /usr/lib/cgi-bin

# enable cgi on apache2 and restart
echo
echo "Enabling CGI on Apache2 and restarting"
echo
a2enmod cgi && service apache2 reload

echo
echo "Downloading Bookworm data"
echo
cd /var/www/
# cd /var/www/BookwormDB
echo "Copy the unshortened Dropbox download link to a bookworm zip and press [Enter]:"
read dropbox
wget "$dropbox"
#mkdir ./drop && wget -O "$dropbox" temp.zip
#unzip temp.zip -d ./drop
#rm -rf *.zip
#cd ./drop
#find . -maxdepth 1 -type d -print -exec mv {} ../files/ \;
#cd ..
#rm -rf ./drop
#make all


echo
echo "Cloning the web app"
echo
cd /var/www/html && mkdir "$bookw" && cd "$bookw"
git clone https://github.com/ddbourgin/bookworm_gui.git
mv ./bookworm_gui/* ./ && rm -rf ./bookworm_gui
# git clone https://github.com/Bookworm-project/BookwormGUI.git
# mv ./BookwormGUI/* ./ && rm -rf ./BookwormGUI

#cp /var/www/bookworm_db/files/*.json ./static/options.json

echo
echo
echo "You're almost done!"
echo "Before everything will be ready, you still need to:"
echo "    1. Unzip the dropbox bookworm file(s) in /www/var/, move them to the bookworm_db/files directory and run 'sudo make all'"
echo "    2. Edit /etc/mysql/my.cnf and change the bind-address to 0.0.0.0 (this allows remote access to the databases)"
echo "    3. Add the line 'user = www-data' under [client] in /etc/mysql/my.cnf"
echo "    4. (optinal) Create a swapfile if the databases are large"
