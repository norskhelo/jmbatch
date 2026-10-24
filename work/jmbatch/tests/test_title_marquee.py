"""Exercise clipped title animation and the card interactions underneath it."""
import tkinter as tk
import unittest
from display_view import DisplayView


class TitleMarqueeTest(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.geometry('420x400')
        self.errors=[];self.root.report_callback_exception=lambda *args:self.errors.append(args)
        self.view=DisplayView(self.root,kind='library',columns=tuple('abcd'),selectmode='extended')
        self.view.pack(fill='both',expand=True)
        for i in range(40):
            self.view.insert('', 'end',iid=str(i),values=('',str(i),'短标题' if i==1 else '完整的长标题\nwith a long ending 终点','ZIP'))
        self.view.set_mode('tiles');self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.assertFalse(self.errors,self.errors)

    def test_single_line_long_title_moves_short_title_stays_and_refresh_keeps_phase(self):
        long=self.view.title_views['0'];short=self.view.title_views['1']
        self.assertNotIn('\n',long.itemcget(long.text_item,'text'))
        self.assertIn('终点',long.itemcget(long.text_item,'text'))
        self.assertGreater(long.overflow,0);self.assertEqual(short.overflow,0)
        long.animate(long.started+1.5);short.animate(short.started+1.5)
        self.assertLess(long.coords(long.text_item)[0],0)
        self.assertEqual(short.coords(short.text_item)[0],1)
        long.animate(long.started+1+long.overflow/30+.5)
        self.assertAlmostEqual(long.coords(long.text_item)[0],1-long.overflow)
        started=long.started
        self.view.item('0',values=('★','0','完整的长标题\nwith a long ending 终点','ZIP'));self.root.update()
        self.assertIs(long,self.view.title_views['0']);self.assertEqual(long.started,started)
        self.assertEqual(long.winfo_width(),int(self.view.cell_width-22))
        self.assertEqual(long.winfo_height(),self.view.tile_font.metrics('linespace'))

    def test_title_pointer_events_keep_parent_coordinates_and_scroll(self):
        title=self.view.title_views['1'];events=[]
        self.view.canvas.bind('<ButtonPress-1>',lambda e:events.append(('press',self.view.identify_at(e.x,e.y))),add='+')
        self.view.canvas.bind('<ButtonRelease-1>',lambda e:events.append(('release',self.view.identify_at(e.x,e.y))),add='+')
        title.event_generate('<ButtonPress-1>',x=4,y=4,time=1000);self.root.update()
        title.event_generate('<ButtonRelease-1>',x=4,y=4,time=1100);self.root.update()
        self.assertEqual(events,[('press','1'),('release','1')])
        self.assertEqual(self.view.selection(),('1',))
        before=self.view.canvas.yview()
        title.event_generate('<MouseWheel>',x=4,y=4,delta=-120,time=1500);self.root.update()
        self.assertGreater(self.view.canvas.yview()[0],before[0])

    def test_offscreen_titles_and_animation_are_cleaned_up(self):
        old=self.view.title_views['0'];self.assertIsNotNone(self.view.marquee_timer)
        self.view.yview_moveto(.8);self.root.update()
        self.assertFalse(old.winfo_exists())
        self.assertEqual(set(self.view.title_views),set(self.view.visible_keys()))
        self.view.set_mode('list');self.root.update()
        self.assertFalse(self.view.title_views);self.assertIsNone(self.view.marquee_timer)
        self.view.set_mode('tiles');self.root.update()
        self.assertTrue(self.view.title_views);self.assertIsNotNone(self.view.marquee_timer)
