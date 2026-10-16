package app.jmbatch.android;

import android.app.Activity;

public final class AlbumScreen {
    public static void show(Activity activity,Store store,LibraryStore.Entry entry){
        ReaderActivity.open(activity,entry);
    }
}
