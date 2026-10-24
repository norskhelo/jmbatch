"""Embedded library layout and page-scoped selection tools."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import queue,threading
from ui_common import *


def build(view,parent):
    view.embedded=parent is not None;view.moving=False;view.sort_mode='name';view.sort_facts={};view.checking_updates=False
    if parent is None:
        view.window=tk.Toplevel(view.app.root);view.window.title('漫画库');view.window.geometry('980x700');view.window.protocol('WM_DELETE_WINDOW',view.close)
    else:
        view.window=ttk.Frame(parent,style='Card.TFrame');view.window.place(x=0,y=0,relwidth=1,relheight=1)
    surface=view.surface=Panel(view.window,padding=18,connected_top=view.embedded);surface.pack(fill='both',expand=True);body=surface.body
    header=ttk.Frame(body);header.pack(fill='x');ttk.Label(header,text='漫画库',font=('Microsoft YaHei UI',22,'bold')).pack(side='left')
    bar=ttk.Frame(body);bar.pack(fill='x',pady=14);bar.columnconfigure(2,weight=1)
    ttk.Button(bar,text='检查更新',command=lambda:check_all(view)).grid(row=0,column=0,sticky='nw',padx=(0,4));view.sort_button=ttk.Button(bar,text='排序方式',command=lambda:sort_menu(view));view.sort_button.grid(row=0,column=1,sticky='nw',padx=4);icon_button(bar,'folder',command=lambda:new_collection(view)).grid(row=0,column=3,sticky='ne',padx=(4,0))

    view.query=tk.StringVar();view.only_favorites=tk.BooleanVar();view.hint=tk.StringVar();view.breadcrumb=tk.StringVar()
    hidden=ttk.Frame(body);view.back_button=ttk.Button(hidden);view.mode_button=ttk.Button(hidden);view.selection_controls=ttk.Frame(hidden);view.stop_button=ttk.Button(hidden);view.display_mode=tk.StringVar(value='tiles')
    holder=ttk.Frame(body);holder.pack(fill='both',expand=True,pady=(8,0))
    from display_view import DisplayView
    view.tree=DisplayView(holder,kind='library',columns=('favorite','id','title','format'),show='tree headings',selectmode='none');view.tree.canvas.configure(bg='white')
    from PIL import Image,ImageTk
    view.cover_placeholder=ImageTk.PhotoImage(Image.new('RGB',(72,96),BG),master=view.window)
    scroll=ttk.Scrollbar(holder,command=view.tree.yview)
    def scrolled(first,last):
        scroll.set(first,last)
        if float(first)>0 or float(last)<1:scroll.pack(side='right',fill='y')
        else:scroll.pack_forget()
    view.tree.configure(yscrollcommand=scrolled);view.tree.pack(fill='both',expand=True);view.tree.set_mode('tiles')
    for event,callback in [('<ButtonPress-1>',view.press),('<ButtonRelease-1>',view.release),('<Double-ButtonPress-1>',view.repeat_press),('<B1-Motion>',view.motion),('<Return>',view.keyboard_activate),('<space>',view.keyboard_activate)]:view.tree.bind(event,callback)
    for event in ('<Leave>','<MouseWheel>','<FocusOut>'):view.tree.bind(event,lambda e:view.cancel_press(),add='+')
    view.tree.bind('<<TreeviewSelect>>',view.details)
    footer=ttk.Frame(body);view.detail=tk.StringVar();view.path_text=tk.StringVar();view.status=tk.StringVar();view.path_entry=ttk.Entry(hidden,textvariable=view.path_text)
    view.sheet_surface=Panel(view.window,padding=22,height=218);view.sheet=view.sheet_surface.body;view.selection_count=tk.StringVar();view.selection_label=ttk.Label(view.sheet,textvariable=view.selection_count,anchor='center',font=('Microsoft YaHei UI',12,'bold'));view.selection_label.pack(fill='x',pady=(0,16))
    view.batch_area=ttk.Frame(view.sheet);view.batch_area.pack(anchor='center');view.action_buttons={};view.batch_rows=[]
    choices=[('导出',lambda:view.action('export'),'export'),('⇧',lambda:share(view),'share'),('删除',lambda:delete_selection(view),'delete'),('收藏',lambda:favorite(view),'favorite'),('移动',lambda:begin_move(view),'collection'),('取消',view.exit_batch,'cancel')]
    for index,(label,command,key) in enumerate(choices):
        button=icon_button(view.batch_area,'share',command=command) if key=='share' else ttk.Button(view.batch_area,text=label,command=command);button.grid(row=index//3,column=index%3,sticky='' if key=='share' else 'ew',padx=4,pady=4);view.batch_area.columnconfigure(index%3,weight=1,uniform='buttons')
        if key!='cancel':view.action_buttons[key]=button
    view.move_area=ttk.Frame(view.sheet);actions(view.move_area,'确认','返回',lambda:commit_move(view),lambda:cancel_move(view))
    view.refresh();view.update_mode();view.cover_timer=view.window.after(100,view.poll_covers);view.window.bind('<Destroy>',view.cover_destroyed,add='+')


def update_mode(view):
    view.tree.selecting=view.batch_mode;view.tree._schedule()
    view.selection_count.set(f'已选中{len(view.tree.selection())}项')
    if view.batch_mode or view.moving:
        bottom=lambda:getattr(view,'page_content_height',view.window.winfo_height())
        new_sheet=not view.sheet_surface.winfo_ismapped();view.sheet_surface.configure(height=118 if view.moving else 218);view.sheet_surface.place(x=1,rely=0,y=bottom()-1,relwidth=1,width=-2,anchor='sw');view.sheet_surface.lift()
        if new_sheet:slide_sheet(view.sheet_surface,bottom=bottom)
        if view.moving:view.batch_area.pack_forget();view.selection_label.pack_forget();view.move_area.pack(fill='x')
        else:view.move_area.pack_forget();view.batch_area.pack(anchor='center');view.selection_label.pack(fill='x',before=view.batch_area)
    else:view.sheet_surface.place_forget()


def new_collection(view):
    dialog,body=modal(view.window);ttk.Label(body,text='新建收藏夹',font=('Microsoft YaHei UI',16,'bold'),anchor='center').pack(fill='x',pady=(0,20));name=Input(body);name.pack(fill='x',pady=(8,12));placeholder(name,'请输入名称')
    def accept():
        try:view.library.create_collection(name.get());dialog.destroy();view.navigate('');view.render()
        except Exception as error:view.messagebox.showerror('无法创建',str(error),parent=dialog)
    actions(body,'确认','取消',accept,dialog.destroy)


def sort_menu(view):
    menu=tk.Menu(view.window,tearoff=False,bg='white')
    def choose(mode):
        if view.busy:return
        view.sort_mode=mode
        if view.sort_mode in ('size','time'):
            def load():
                facts={}
                for key,item in view.library.entries.items():
                    try:
                        path=Path(item['path']);st=path.stat()
                        if view.sort_mode=='time':facts[key]=st.st_mtime
                        elif view.sort_mode=='size':facts[key]=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink()) if path.is_dir() else st.st_size
                    except (OSError,ValueError):facts[key]=-1
                return facts
            view.run(load,lambda facts:(setattr(view,'sort_facts',facts),view.render()))
        else:view.render()
    for label,value in [('名称','name'),('时间','time'),('大小','size'),('章节数','chapters')]:menu.add_command(label=label,command=lambda m=value:choose(m))
    menu.tk_popup(view.sort_button.winfo_rootx(),view.sort_button.winfo_rooty()+view.sort_button.winfo_height())


def sorted_items(view,items):
    from name_sort import name_key
    facts=({key:item.get('chapter_count',-1) for key,item in view.library.entries.items()}
           if view.sort_mode=='chapters' else dict(view.sort_facts))
    if view.sort_mode!='name':
        folders={key:0 for key,item in items if item.get('format')=='collection'}
        for key,item in view.library.entries.items():
            folder=item.get('collection','')
            if folder in folders:
                value=max(0,facts.get(key,0))
                folders[folder]=max(folders[folder],value) if view.sort_mode=='time' else folders[folder]+value
        facts.update(folders)
    def key(pair):
        identity,item=pair
        group=0 if item.get('format')=='collection' else 1 if item.get('favorite') else 2
        title=name_key(item['title'])
        return group,title if view.sort_mode=='name' else facts.get(identity,0),title
    return sorted(items,key=key)


def prepare_chapter_counts(view):
    """Populate legacy metadata without blocking the library or a sort change."""
    if getattr(view,'chapter_scan_running',False):return
    attempted=getattr(view,'chapter_scan_attempted',set())
    items=[(key,dict(item)) for key,item in view.library.entries.items()
           if item.get('chapter_count',-1)<0 and key not in attempted]
    if not items:return
    view.chapter_scan_attempted=attempted|{key for key,_ in items}
    view.chapter_scan_running=True;results=queue.Queue()
    def scan():
        try:results.put((view.library.read_chapter_counts(items),None))
        except Exception as error:results.put(({},str(error)))
    def poll():
        if view.busy or results.empty():view.chapter_scan_timer=view.window.after(100,poll);return
        view.chapter_scan_timer=None
        counts,error=results.get();view.chapter_scan_running=False
        try:
            if error:raise OSError(error)
            changed=view.library.save_chapter_counts(counts)
        except Exception as error:
            view.status.set('章节信息保存失败：'+str(error));return
        if changed:view.render()
        else:prepare_chapter_counts(view)
    threading.Thread(target=scan,daemon=True).start();view.chapter_scan_timer=view.window.after(100,poll)


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
        holder=ttk.Frame(body)
        if any(len(p['chapters'])>1 for p in plans.values()):holder.pack(fill='x',pady=15)
        canvas=tk.Canvas(holder,height=260,highlightthickness=0,bg='white',yscrollincrement=1);scroll=ttk.Scrollbar(holder,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set);inner=ttk.Frame(canvas);item=canvas.create_window(0,0,anchor='nw',window=inner);canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width));inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));dialog.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120)*32,'units'))
        choices={}
        for key,plan in plans.items():
            choices[key]={}
            if len(plan['chapters'])>1:ttk.Label(inner,text=view.library.entries[key]['title'],font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=6)
            for chapter,count in plan['chapters'].items():
                value=tk.BooleanVar(value=True);choices[key][chapter]=value
                if len(plan['chapters'])>1:ttk.Checkbutton(inner,text=f'第 {chapter} 章 · {count} 页',variable=value).pack(anchor='w')
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
