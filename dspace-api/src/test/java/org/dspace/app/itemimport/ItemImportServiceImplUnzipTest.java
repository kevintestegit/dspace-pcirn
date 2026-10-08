/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.itemimport;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import org.dspace.services.ConfigurationService;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

/** Tests bounded SAF extraction using real, small ZIP archives without application services. */
public class ItemImportServiceImplUnzipTest {
    private static final String PREFIX = "org.dspace.app.batchitemimport.zip.";

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private ItemImportServiceImpl service;
    private ConfigurationService configuration;
    private Path destination;

    @Before
    public void setUp() throws Exception {
        service = new ItemImportServiceImpl();
        configuration = mock(ConfigurationService.class);
        when(configuration.getIntProperty(anyString(), anyInt())).thenAnswer(call -> call.getArgument(1));
        when(configuration.getLongProperty(anyString(), anyLong())).thenAnswer(call -> call.getArgument(1));
        destination = temporaryFolder.newFolder("destination").toPath();
        service.configurationService = configuration;
        service.tempWorkDir = destination.toString();
    }

    @Test
    public void rejectsNonZipInputAndCleansExtractionRoot() throws Exception {
        File archive = temporaryFolder.newFile("not-a-zip.zip");
        Files.write(archive.toPath(), bytes("not a ZIP archive"));

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void chargesDirectoryPayloadAgainstExpandedByteLimit() throws Exception {
        when(configuration.getLongProperty(PREFIX + "max-entry-bytes", 1073741824L)).thenReturn(4L);
        File archive = zip(new String[] {"item/"}, new byte[][] {bytes("12345")});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void createsMissingCallerDestinationDirectory() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("ok")});
        destination = destination.resolve("data_unzipped2");

        assertEquals(extractionRoot(archive).toString(), service.unzip(archive, destination.toString()));
        assertArrayEquals(bytes("ok"), Files.readAllBytes(extractionRoot(archive).resolve("item/contents")));
    }

    @Test
    public void extractsNormalSafAndReturnsArchiveRoot() throws Exception {
        File archive = zip(new String[] {"item/", "item/contents", "item/dublin_core.xml"},
                           new byte[][] {new byte[0], bytes("document.pdf"), bytes("<dublin_core/>")});

        assertEquals(extractionRoot(archive).toString(), service.unzip(archive, destination.toString()));
        assertArrayEquals(bytes("document.pdf"), Files.readAllBytes(extractionRoot(archive).resolve("item/contents")));
    }

    @Test
    public void preservesWrappedSafSourceDirectoryAndDefaultWorkDirectory() throws Exception {
        File archive = zip(new String[] {"SimpleArchiveFormat/item/contents"}, new byte[][] {bytes("document.pdf")});

        assertEquals(extractionRoot(archive).resolve("SimpleArchiveFormat").toString(), service.unzip(archive, null));
        assertArrayEquals(bytes("document.pdf"),
                          Files.readAllBytes(extractionRoot(archive).resolve("SimpleArchiveFormat/item/contents")));
    }

    @Test
    public void acceptsEntryAndTotalByteLimitsExactly() throws Exception {
        when(configuration.getLongProperty(PREFIX + "max-entry-bytes", 1073741824L)).thenReturn(4L);
        when(configuration.getLongProperty(PREFIX + "max-total-bytes", 10737418240L)).thenReturn(8L);
        when(configuration.getIntProperty(PREFIX + "max-entries", 10000)).thenReturn(2);
        File archive = zip(new String[] {"item/first", "item/second"}, new byte[][] {bytes("1234"), bytes("5678")});

        assertEquals(extractionRoot(archive).toString(), service.unzip(archive, destination.toString()));
        assertArrayEquals(bytes("5678"), Files.readAllBytes(extractionRoot(archive).resolve("item/second")));
    }

    @Test
    public void boundsImplicitDirectoriesFromDeepEntryPaths() throws Exception {
        when(configuration.getIntProperty(PREFIX + "max-entries", 10000)).thenReturn(1);
        File archive = zip(new String[] {"a/b/c/d/contents"}, new byte[][] {new byte[0]});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void rejectsTooManyEntriesIncludingDirectoriesAndRemovesPartialExtraction() throws Exception {
        when(configuration.getIntProperty(PREFIX + "max-entries", 10000)).thenReturn(2);
        File archive = zip(new String[] {"item/", "item/contents", "item/dublin_core.xml"},
                           new byte[][] {new byte[0], bytes("first"), bytes("second")});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void rejectsEntryByteOverflowAndRemovesPartialExtraction() throws Exception {
        when(configuration.getLongProperty(PREFIX + "max-entry-bytes", 1073741824L)).thenReturn(4L);
        File archive = zip(new String[] {"item/first", "item/oversized"}, new byte[][] {bytes("1234"), bytes("12345")});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void rejectsTotalExpandedByteOverflowAndRemovesPartialExtraction() throws Exception {
        when(configuration.getLongProperty(PREFIX + "max-total-bytes", 10737418240L)).thenReturn(7L);
        File archive = zip(new String[] {"item/first", "item/second"}, new byte[][] {bytes("1234"), bytes("5678")});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void rejectsExcessiveCompressionExpansionAndRemovesPartialExtraction() throws Exception {
        when(configuration.getIntProperty(PREFIX + "max-expansion-ratio", 100)).thenReturn(2);
        File archive = zip(new String[] {"item/first", "item/compressed"}, new byte[][] {bytes("ok"), new byte[4096]});

        assertRejectedAndCleaned(archive);
    }

    @Test
    public void rejectsTraversalAndRemovesEarlierExtractedEntries() throws Exception {
        File archive = zip(new String[] {"item/first", "../escaped"}, new byte[][] {bytes("ok"), bytes("outside")});

        assertRejectedAndCleaned(archive);
        assertFalse(Files.exists(destination.resolve("escaped")));
    }

    @Test
    public void rejectsExistingExtractionDirectoryWithoutOverwritingItsFiles() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("replacement")});
        Path existing = Files.createDirectories(extractionRoot(archive).resolve("item"));
        Path contents = Files.write(existing.resolve("contents"), bytes("original"));

        assertThrows(IOException.class, () -> service.unzip(archive, destination.toString()));
        assertArrayEquals(bytes("original"), Files.readAllBytes(contents));
    }

    @Test
    public void rejectsNonpositiveEntryCounts() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("ok")});
        for (int invalid : new int[] {0, -1}) {
            when(configuration.getIntProperty(PREFIX + "max-entries", 10000)).thenReturn(invalid);
            assertRejectedAndCleaned(archive);
        }
    }

    @Test
    public void rejectsNonpositiveEntryByteLimits() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("ok")});
        for (long invalid : new long[] {0, -1}) {
            when(configuration.getLongProperty(PREFIX + "max-entry-bytes", 1073741824L)).thenReturn(invalid);
            assertRejectedAndCleaned(archive);
        }
    }

    @Test
    public void rejectsNonpositiveTotalByteLimits() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("ok")});
        for (long invalid : new long[] {0, -1}) {
            when(configuration.getLongProperty(PREFIX + "max-total-bytes", 10737418240L)).thenReturn(invalid);
            assertRejectedAndCleaned(archive);
        }
    }

    @Test
    public void rejectsNonpositiveExpansionRatios() throws Exception {
        File archive = zip(new String[] {"item/contents"}, new byte[][] {bytes("ok")});
        for (int invalid : new int[] {0, -1}) {
            when(configuration.getIntProperty(PREFIX + "max-expansion-ratio", 100)).thenReturn(invalid);
            assertRejectedAndCleaned(archive);
        }
    }

    private void assertRejectedAndCleaned(File archive) throws Exception {
        assertThrows(IOException.class, () -> service.unzip(archive, destination.toString()));
        assertFalse("Rejected archives must leave no partial extraction", Files.exists(extractionRoot(archive)));
    }

    private Path extractionRoot(File archive) {
        return destination.resolve(archive.getName());
    }

    private File zip(String[] names, byte[][] contents) throws IOException {
        File archive = temporaryFolder.newFile("saf.zip");
        try (ZipOutputStream output = new ZipOutputStream(Files.newOutputStream(archive.toPath()))) {
            for (int index = 0; index < names.length; index++) {
                output.putNextEntry(new ZipEntry(names[index]));
                output.write(contents[index]);
                output.closeEntry();
            }
        }
        return archive;
    }

    private static byte[] bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }
}
