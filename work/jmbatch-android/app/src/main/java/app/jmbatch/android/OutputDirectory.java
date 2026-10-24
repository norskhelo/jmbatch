package app.jmbatch.android;

import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.DocumentsContract;
import java.io.File;

/** Display the download destination without changing its persisted SAF grant. */
final class OutputDirectory {
    private OutputDirectory() {}

    static String display(Context context, String outputUri) {
        if (outputUri == null || outputUri.isEmpty())
            return AlbumStorage.root(context).getAbsolutePath();
        try {
            Uri tree = Uri.parse(outputUri);
            if ("content".equals(tree.getScheme()) &&
                    "com.android.externalstorage.documents".equals(tree.getAuthority())) {
                String id = DocumentsContract.getTreeDocumentId(tree);
                int colon = id.indexOf(':');
                if (colon >= 0) {
                    File root = volumeRoot(context, id.substring(0, colon));
                    if (root != null) {
                        String relative = id.substring(colon + 1);
                        // Only display a filesystem path when it stays inside this volume.
                        File target = relative.isEmpty() ? root : new File(root, relative);
                        File canonicalRoot = root.getCanonicalFile(), canonical = target.getCanonicalFile();
                        if (canonical.equals(canonicalRoot) || canonical.getPath().startsWith(canonicalRoot.getPath() + File.separator))
                            return target.getAbsolutePath();
                    }
                }
            }
        } catch (Exception ignored) {
            // Unmounted volumes and opaque document providers retain their exact address.
        }
        return outputUri;
    }

    private static boolean matches(StorageVolume volume, String id) {
        return volume != null && ("primary".equals(id) ? volume.isPrimary() : id.equalsIgnoreCase(volume.getUuid()));
    }

    private static File volumeRoot(Context context, String id) {
        StorageManager manager = (StorageManager) context.getSystemService(Context.STORAGE_SERVICE);
        if (manager == null) return null;
        if (Build.VERSION.SDK_INT >= 30) {
            for (StorageVolume volume : manager.getStorageVolumes())
                if (matches(volume, id) && volume.getDirectory() != null) return volume.getDirectory();
        }
        // Android 8–10 expose per-volume app directories, but no public volume root API.
        String suffix = "/Android/data/" + context.getPackageName() + "/files";
        for (File directory : context.getExternalFilesDirs(null)) {
            if (directory == null || !matches(manager.getStorageVolume(directory), id)) continue;
            String path = directory.getAbsolutePath();
            if (path.endsWith(suffix)) return new File(path.substring(0, path.length() - suffix.length()));
        }
        return null;
    }
}
