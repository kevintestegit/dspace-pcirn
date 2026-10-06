/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.sword2;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import org.dspace.app.util.LimitedInputStream;

/**
 * Fully validate and bound ZIP expansion before any bitstream is persisted.
 */
final class StagedZip implements AutoCloseable {
    private final Path directory;
    private final List<Path> files = new ArrayList<>();
    private final List<String> names = new ArrayList<>();

    private StagedZip(Path directory) {
        this.directory = directory;
    }

    static StagedZip expand(File archive, int maxEntries, long maxEntryBytes, long maxTotalBytes, int maxRatio)
        throws IOException {
        if (maxEntries <= 0 || maxEntryBytes <= 0 || maxTotalBytes <= 0 || maxRatio <= 0) {
            throw new IOException("ZIP expansion limits must be positive");
        }
        StagedZip staged = new StagedZip(Files.createTempDirectory("dspace-sword-zip-"));
        try (ZipFile zip = new ZipFile(archive)) {
            if (zip.size() > maxEntries) {
                throw new IOException("Too many ZIP entries");
            }
            long total = 0;
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                Path name = Path.of(entry.getName()).normalize();
                if (name.isAbsolute() || name.startsWith("..") || entry.getName().contains("\\")) {
                    throw new IOException("Invalid ZIP entry path");
                }
                if (entry.isDirectory()) {
                    continue;
                }
                long compressed = entry.getCompressedSize();
                if (compressed < 0) {
                    throw new IOException("Unknown ZIP compressed size");
                }
                long ratioBudget = compressed > Long.MAX_VALUE / maxRatio ? Long.MAX_VALUE : compressed * maxRatio;
                long budget = Math.min(Math.min(maxEntryBytes, maxTotalBytes - total), ratioBudget);
                Path output = Files.createTempFile(staged.directory, "entry-", ".bin");
                staged.files.add(output);
                staged.names.add(entry.getName());
                try (InputStream input = new LimitedInputStream(zip.getInputStream(entry), budget)) {
                    try (java.io.OutputStream target = Files.newOutputStream(output)) {
                        input.transferTo(target);
                    }
                }
                total += Files.size(output);
            }
            return staged;
        } catch (IOException | RuntimeException e) {
            try {
                staged.close();
            } catch (IOException cleanupError) {
                e.addSuppressed(cleanupError);
            }
            throw e;
        }
    }

    List<Path> files() {
        return files;
    }

    String name(int index) {
        return names.get(index);
    }

    @Override
    public void close() throws IOException {
        IOException failure = null;
        for (Path file : files) {
            try {
                Files.deleteIfExists(file);
            } catch (IOException e) {
                if (failure == null) {
                    failure = e;
                } else {
                    failure.addSuppressed(e);
                }
            }
        }
        try {
            Files.deleteIfExists(directory);
        } catch (IOException e) {
            if (failure == null) {
                failure = e;
            } else {
                failure.addSuppressed(e);
            }
        }
        if (failure != null) {
            throw failure;
        }
    }
}
