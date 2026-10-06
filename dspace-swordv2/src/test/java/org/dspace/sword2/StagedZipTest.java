/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.sword2;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Tests bounded staging before bitstream persistence. */
public class StagedZipTest {
    @Rule
    public TemporaryFolder temporary = new TemporaryFolder();

    @Test
    public void preservesOrdinaryEntriesAndCleansStaging() throws Exception {
        Path archive = archive(new String[] {"folder/", "folder/content.txt"}, new byte[] {1, 2, 3});
        Path stagedFile;
        try (StagedZip staged = StagedZip.expand(archive.toFile(), 10, 100, 100, 100)) {
            assertEquals(1, staged.files().size());
            assertEquals("folder/content.txt", staged.name(0));
            stagedFile = staged.files().get(0);
            assertArrayEquals(new byte[] {1, 2, 3}, Files.readAllBytes(stagedFile));
        }
        org.junit.Assert.assertFalse(Files.exists(stagedFile.getParent()));
    }

    @Test
    public void rejectsEntryCountAndExpandedBytes() throws Exception {
        Path archive = archive(new String[] {"first", "second"}, new byte[20]);
        long before = stagingDirectories();
        assertThrows(IOException.class, () -> StagedZip.expand(archive.toFile(), 1, 100, 100, 100));
        assertThrows(IOException.class, () -> StagedZip.expand(archive.toFile(), 10, 10, 100, 100));
        assertThrows(IOException.class, () -> StagedZip.expand(archive.toFile(), 10, 100, 30, 100));
        assertEquals(before, stagingDirectories());
    }

    @Test
    public void rejectsCompressionBombAndTraversal() throws Exception {
        Path bomb = archive(new String[] {"bomb"}, new byte[100000]);
        assertThrows(IOException.class, () -> StagedZip.expand(bomb.toFile(), 10, 200000, 200000, 10));
        for (String name : new String[] {"../escape", "/absolute", "..\\escape"}) {
            Path archive = archive(new String[] {name}, new byte[1]);
            assertThrows(IOException.class, () -> StagedZip.expand(archive.toFile(), 10, 100, 100, 100));
        }
    }

    @Test
    public void cannotDisableExpansionLimits() throws Exception {
        Path archive = archive(new String[] {"content"}, new byte[1]);
        assertThrows(IOException.class, () -> StagedZip.expand(archive.toFile(), 0, 100, 100, 100));
    }

    private Path archive(String[] names, byte[] bytes) throws Exception {
        Path file = temporary.newFile().toPath();
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(file))) {
            for (String name : names) {
                zip.putNextEntry(new ZipEntry(name));
                if (!name.endsWith("/")) {
                    zip.write(bytes);
                }
                zip.closeEntry();
            }
        }
        return file;
    }

    private long stagingDirectories() throws IOException {
        try (java.util.stream.Stream<Path> paths = Files.list(Path.of(System.getProperty("java.io.tmpdir")))) {
            return paths.filter(path -> path.getFileName().toString().startsWith("dspace-sword-zip-")).count();
        }
    }
}
