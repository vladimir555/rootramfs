if [ ! -d "$1" ]; then
    echo $0 " dir_path, dir '" $1 "' not found"
    exit 1
fi
current_dir="$PWD"
cd $1 &&
find -type f -exec md5sum {} \; | awk -F'  ./' '{print $1"  "$2}' > DEBIAN/md5sums &&
cd "$current_dir" &&
dpkg --build "$1" &&
echo DONE && exit 0 ||
echo FAIL && exit 1