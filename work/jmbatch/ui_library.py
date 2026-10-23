"""Embedded library layout and page-scoped selection tools."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import queue,threading
from ui_common import *


def build(view,parent):
    view.embedded=parent is not None;view.moving=False;view.sort_mode='name';view.sort_reverse=False;view.sort_facts={};view.checking_updates=False
    if parent is None:
        view.window=tk.Toplevel(view.app.root);view.window.title('漫画库');view.window.geometry('980x700');view.window.protocol('WM_DELETE_WINDOW',view.close)
    else:
        view.window=ttk.Frame(parent,style='Card.TFrame');view.window.place(x=0,y=0,relwidth=1,relheight=1)
    body=ttk.Frame(view.window,padding=18,style='Card.TFrame');body.pack(fill='both',expand=True)
    header=ttk.Frame(body);header.pack(fill='x');ttk.Label(header,text='漫画库',font=('Microsoft YaHei UI',22,'bold')).pack(side='left');ttk.Button(header,text='下载页面 ↓',command=lambda:__import__('ui_main').hide_library(view.app)).pack(side='right')
    bar=ttk.Frame(body);bar.pack(fill='x',pady=14);ttk.Button(bar,text='检查更新',command=lambda:check_all(view)).pack(side='left');view.sort_button=ttk.Button(bar,text='排序方式（正序）⌄',command=lambda:sort_menu(view));view.sort_button.pack(side='left',padx=8);ttk.Button(bar,text='⊞ 新建收藏夹',command=lambda:new_collection(view)).pack(side='right')
    view.query=tk.StringVar();view.only_favorites=tk.BooleanVar();view.hint=tk.StringVar();view.breadcrumb=tk.StringVar();ttk.Label(body,textvariable=view.breadcrumb,foreground=MUTED).pack(anchor='w')
    hidden=ttk.Frame(body);view.back_button=ttk.Button(hidden);view.mode_button=ttk.Button(hidden);view.selection_controls=ttk.Frame(hidden);view.stop_button=ttk.Button(hidden);view.display_mode=tk.StringVar(value='tiles')
    holder=ttk.Frame(body);holder.pack(fill='both',expand=True,pady=(8,0))
    from display_view import DisplayView
    view.tree=DisplayView(holder,kind='library',columns=('favorite','id','title','format'),show='tree headings',selectmode='none');view.tree.canvas.configure(bg='white')
    from PIL import Image,ImageTk
    view.cover_placeholder=ImageTk.PhotoImage(Image.new('RGB',(72,96),BG),master=view.window)
    scroll=ttk.Scrollbar(holder,command=view.tree.yview);scroll.pack(side='right',fill='y');view.tree.configure(yscrollcommand=scroll.set);view.tree.pack(fill='both',expand=True);view.tree.set_mode('tiles')
    for event,callback in [('<ButtonPress-1>',view.press),('<ButtonRelease-1>',view.release),('<Double-ButtonPress-1>',view.repeat_press),('<B1-Motion>',view.motion),('<Return>',view.keyboard_activate),('<space>',view.keyboard_activate)]:view.tree.bind(event,callback)
    for event in ('<Leave>','<MouseWheel>','<FocusOut>'):view.tree.bind(event,lambda e:view.cancel_press(),add='+')
    view.tree.bind('<<TreeviewSelect>>',view.details)
    footer=ttk.Frame(body);footer.pack(fill='x',pady=(8,0));view.detail=tk.StringVar();view.path_text=tk.StringVar();view.status=tk.StringVar();view.path_entry=ttk.Entry(hidden,textvariable=view.path_text);ttk.Label(footer,textvariable=view.status,foreground=MUTED).pack(side='left');ttk.Button(footer,text='扫描保存目录',command=view.scan).pack(side='right')
    view.sheet=ttk.Frame(view.window,padding=22,style='Card.TFrame');view.selection_count=tk.StringVar();view.selection_label=ttk.Label(view.sheet,textvariable=view.selection_count,anchor='center',font=('Microsoft YaHei UI',12,'bold'));view.selection_label.pack(fill='x',pady=(0,16))
    view.batch_area=ttk.Frame(view.sheet);view.batch_area.pack(fill='x');view.action_buttons={};view.batch_rows=[]
    choices=[('导出',lambda:view.action('export'),'export'),('删除',lambda:delete_selection(view),'delete'),('分享',lambda:share(view),'share'),('收藏',lambda:favorite(view),'favorite'),('移动',lambda:begin_move(view),'collection'),('取消',view.exit_batch,'cancel')]
    for index,(label,command,key) in enumerate(choices):
        button=ttk.Button(view.batch_area,text=label,command=command);button.grid(row=index//3,column=index%3,sticky='ew',padx=4,pady=4);view.batch_area.columnconfigure(index%3,weight=1,uniform='buttons')
        if key!='cancel':view.action_buttons[key]=button
    view.move_area=ttk.Frame(view.sheet);actions(view.move_area,'确认','返回',lambda:commit_move(view),lambda:cancel_move(view))
    view.refresh();view.update_mode();view.cover_timer=view.window.after(100,view.poll_covers);view.window.bind('<Destroy>',view.cover_destroyed,add='+')


def update_mode(view):
    view.selection_count.set(f'已选中{len(view.tree.selection())}项')
    if view.batch_mode or view.moving:
        view.sheet.place(x=1,rely=1,y=-1,relwidth=1,width=-2,anchor='sw');view.sheet.lift()
        if view.moving:view.batch_area.pack_forget();view.selection_label.pack_forget();view.move_area.pack(fill='x')
        else:view.move_area.pack_forget();view.selection_label.pack(fill='x',before=view.batch_area);view.batch_area.pack(fill='x')
    else:view.sheet.place_forget()


def new_collection(view):
    dialog,body=modal(view.window);ttk.Label(body,text='新建收藏夹',font=('Microsoft YaHei UI',16,'bold'),anchor='center').pack(fill='x',pady=(0,20));name=ttk.Entry(body);name.pack(fill='x');placeholder(name,'请输入名称')
    def accept():
        try:view.library.create_collection(name.get());dialog.destroy();view.navigate('');view.render()
        except Exception as error:view.messagebox.showerror('无法创建',str(error),parent=dialog)
    actions(body,'确认','取消',accept,dialog.destroy)


def sort_menu(view):
    menu=tk.Menu(view.window,tearoff=False,bg='white')
    def choose(mode):
        if mode=='reverse':view.sort_reverse=not view.sort_reverse
        else:view.sort_mode=mode
        view.sort_button.configure(text='排序方式（'+('倒序' if view.sort_reverse else '正序')+'）⌄')
        if view.sort_mode in ('size','chapters','time'):
            def load():
                facts={}
                from reader import ReaderSource
                for key,item in view.library.entries.items():
                    try:
                        path=Path(item['path']);st=path.stat()
                        if view.sort_mode=='time':facts[key]=st.st_mtime
                        elif view.sort_mode=='size':facts[key]=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink()) if path.is_dir() else st.st_size
                        else:
                            source=ReaderSource(path)
                            try:facts[key]=len({page['chapter'] for page in source.pages})
                            finally:source.close()
                    except (OSError,ValueError):facts[key]=-1
                return facts
            view.run(load,lambda facts:(setattr(view,'sort_facts',facts),view.render()))
        else:view.render()
    for label,value in [('名称','name'),('时间','time'),('大小','size'),('章节数','chapters'),('改为正序' if view.sort_reverse else '改为倒序','reverse')]:menu.add_command(label=label,command=lambda m=value:choose(m))
    menu.tk_popup(view.sort_button.winfo_rootx(),view.sort_button.winfo_rooty()+view.sort_button.winfo_height())


def sorted_items(view,items):
    favorites=[pair for pair in items if pair[1].get('favorite')];rest=[pair for pair in items if not pair[1].get('favorite')]
    key=(lambda pair:pair[1]['title'].casefold()) if view.sort_mode=='name' else (lambda pair:view.sort_facts.get(pair[0],0))
    return favorites+sorted(rest,key=key,reverse=view.sort_reverse)


def favorite(view):
    keys=view.tree.selection();value=not all(view.library.entries[k]['favorite'] for k in keys if k in view.library.entries);view.library.set_favorites(keys,value);view.render()


def begin_move(view):
    view.moving_keys=list(view.tree.selection());view.move_origin=view.collection;view.moving=True;view.batch_mode=False;view.collection='';view.render();update_mode(view)


def cancel_move(view):
    view.moving=False;view.collection=view.move_origin;view.render();update_mode(view)


def commit_move(view):
    try:view.library.move_to_collection(view.moving_keys,view.collection);view.moving=False;view.render();update_mode(view)
    except Exception as e:view.messagebox.showerror('移动失败',str(e),parent=view.window)


def share(view):
    keys=view.tree.selection()
    if any(view.library.entries[k]['format']=='images' for k in keys):view.messagebox.showinfo('分享','图片文件夹请先导出为 pdf 或 zip。',parent=view.window);return
    if not keys:return
    from windows_share import prepare,show
    def operation():
        files=[view.library.checked_path(key) for key in keys]
        path=prepare(files,view.app.home,view.cancelled.is_set);show(path)
        return '已打开系统分享；多选文件保存在 '+str(path) if len(files)>1 else '已打开系统分享'
    view.run(operation,view.status.set)


def delete_selection(view):
    keys=list(view.tree.selection())
    if not keys:return
    from chapter_delete import inspect,delete_chapters
    def prepared(plans):
        dialog,body=modal(view.window,500,blur=True);ttk.Label(body,text='是否删除文件',font=('Microsoft YaHei UI',14,'bold'),anchor='center').pack(fill='x')
        holder=ttk.Frame(body);holder.pack(fill='x',pady=15)
        canvas=tk.Canvas(holder,height=260,highlightthickness=0,bg='white',yscrollincrement=1);scroll=ttk.Scrollbar(holder,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set);inner=ttk.Frame(canvas);item=canvas.create_window(0,0,anchor='nw',window=inner);canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));dialog.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120)*32,'units'))
        choices={}
        for key,plan in plans.items():
            ttk.Label(inner,text=view.library.entries[key]['title'],font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=6);choices[key]={}
            for chapter,count in plan['chapters'].items():
                value=tk.BooleanVar(value=True);choices[key][chapter]=value;ttk.Checkbutton(inner,text=f'第 {chapter} 章 · {count} 页' if len(plan['chapters'])>1 else '整本漫画',variable=value).pack(anchor='w')
        def remove():
            selected={key:{c for c,v in rows.items() if v.get()} for key,rows in choices.items()};dialog.destroy()
            def operation():
                whole=[];messages=[]
                for key,chapters in selected.items():
                    if not chapters:continue
                    if len(chapters)==len(plans[key]['chapters']):whole.append(key)
                    else:delete_chapters(view.app.engine,key,chapters,plans[key],view.cancelled.is_set);messages.append(f'已删除 {len(chapters)} 章')
                if whole:
                    done,errors,remaining=view.library.remove_many(whole,view.app.engine.tasks,True,view.cancelled,lambda d,t:None);messages.append(f'已删除 {len(done)} 本；失败 {len(errors)} 本')
                    if errors:messages.extend(str(e) for _,e in errors)
                return '\n'.join(messages)
            view.run(operation,lambda text:(view.status.set(text),view.exit_batch()),True)
        actions(body,'确认','取消',remove,dialog.destroy)
    view.run(lambda:{key:inspect(view.library,key) for key in keys},prepared,True)


def check_all(view):
    if view.checking_updates:return
    try:settings=view.app.current_settings()
    except ValueError as error:view.messagebox.showerror('设置无效',str(error),parent=view.window);return
    view.checking_updates=True;notice(view.app.root,'开始检查章节更新');events=queue.Queue();cookie=view.app.engine.cookie;items=list(view.library.entries.items());cancelled=threading.Event();view.update_cancelled=cancelled
    def work():
        from chapter_updates import UpdateHistory,fetch_catalog
        found=[];errors=[]
        try:
            history=UpdateHistory(view.app.home);history.record(view.app.engine.tasks)
            seen=set()
            for key,item in items:
                if cancelled.is_set():break
                if not item['id'].isdigit() or item['id'] in seen:continue
                seen.add(item['id'])
                try:
                    from reader import ReaderSource
                    source=ReaderSource(item['path'])
                    try:multiple=len({page['chapter'] for page in source.pages})>1
                    finally:source.close()
                    if not multiple:continue
                    catalog=fetch_catalog(item['id'],settings,cookie,cancelled)
                    if len(catalog)>1:
                        fresh,_=history.compare(item['id'],catalog)
                        if fresh:found.append((item,catalog,fresh))
                except Exception as e:errors.append(str(e))
        except Exception as e:errors.append(str(e))
        events.put((found,errors))
    threading.Thread(target=work,daemon=True).start()
    def poll():
        if not view.window.winfo_exists():cancelled.set();return
        try:found,errors=events.get_nowait()
        except queue.Empty:view.window.after(100,poll);return
        view.checking_updates=False;notice(view.app.root,'检查完成'+(f'，{len(errors)} 项失败' if errors else ''))
        if not found:return
        def download():
            failed=[]
            for item,catalog,fresh in found:
                try:view.app.engine.add_chapter_update(item['id'],catalog,fresh,settings)
                except Exception as error:failed.append(str(error))
            view.app.render()
            if failed:view.messagebox.showwarning('部分任务未加入','\n'.join(failed),parent=view.window)
        confirm(view.window,'发现新章节，是否下载？\n'+'\n'.join(f"{item['title']} · {len(fresh)} 章" for item,_,fresh in found),download)
    view.window.after(100,poll)
