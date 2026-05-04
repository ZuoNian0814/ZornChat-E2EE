import os, datetime

class DirAnalys:
    def __init__(self, dir_path):
        self.dir_path = dir_path
        self.analys_path_l = len(dir_path)+1
        self.item_path_dict = {}

    def recursion_analys(self, analys_path=None):
        if analys_path is None:
            path = self.dir_path
        else:
            path = analys_path
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                relative_name = item_path[self.analys_path_l:]
                self.item_path_dict[relative_name] = item_path
            elif os.path.isdir(item_path):
                self.recursion_analys(item_path)
        # 第一个用作配置说明，第二个用于打包和位置声明
        return self.item_path_dict

    def get_file_size(self, file_path):
        size = os.path.getsize(file_path)
        if size >= 1024**3:
            return f"{size / 1024**3:.2f} GB"
        elif size >= 1024**2:
            return f"{size / 1024**2:.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size} B"

    def list_dir_contents(self, path):
        data = {'file': [], 'folder': []}
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                data['file'].append(item_path)
            elif os.path.isdir(item_path):
                data['folder'].append(item_path)

        folder_config = []
        for folder in data['folder']:
            folder_name = os.path.basename(folder)
            folder_type = 'Folder'

            # 获取文件的创建时间
            creation_time = os.path.getctime(folder)
            # 将时间戳转换为可读的时间格式
            creation_time_str = datetime.datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
            folder_config.append([folder_name, creation_time_str, folder_type, ''])
        for file in data['file']:
            file_name = os.path.basename(file)
            f_type = file_name.split('.')[-1].upper()
            file_b = self.get_file_size(file)
            creation_time = os.path.getctime(file)
            creation_time_str = datetime.datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d %H:%M:%S')
            folder_config.append([file_name, creation_time_str, f_type, file_b])
        return folder_config