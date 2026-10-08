/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.storage.bitstore;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import org.dspace.content.Bitstream;
import org.dspace.content.service.BitstreamService;
import org.dspace.core.Context;
import org.dspace.services.ConfigurationService;
import org.dspace.services.factory.DSpaceServicesFactory;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.mockito.MockedStatic;

/**
 * Migration safety tests using disposable files and a simulated metadata transaction.
 */
public class BitstreamStorageServiceImplTest {
    private static final byte[] CONTENT = "assetstore migration must retain these bytes".getBytes(UTF_8);

    @Rule
    public final TemporaryFolder temporaryFolder = new TemporaryFolder();

    private final Context context = mock(Context.class);
    private final BitstreamService bitstreamService = mock(BitstreamService.class);
    private final BitstreamStorageServiceImpl storage = new BitstreamStorageServiceImpl();
    private DSBitStoreService source;
    private DSBitStoreService destination;
    private MockedStatic<DSpaceServicesFactory> servicesFactory;

    @Before
    public void setUp() throws Exception {
        ConfigurationService configuration = mock(ConfigurationService.class);
        when(configuration.getArrayProperty(anyString(), any(String[].class))).thenReturn(new String[0]);
        DSpaceServicesFactory factory = mock(DSpaceServicesFactory.class);
        when(factory.getConfigurationService()).thenReturn(configuration);
        servicesFactory = mockStatic(DSpaceServicesFactory.class);
        servicesFactory.when(DSpaceServicesFactory::getInstance).thenReturn(factory);
        source = store(temporaryFolder.newFolder("source"));
        destination = spy(store(temporaryFolder.newFolder("destination")));
        Map<Integer, BitStoreService> stores = new HashMap<>();
        stores.put(0, source);
        stores.put(1, destination);
        storage.setStores(stores);
        storage.bitstreamService = bitstreamService;
        when(context.isValid()).thenReturn(true);
    }

    @After
    public void tearDown() {
        servicesFactory.close();
    }

    @Test
    public void rejectsSameStoreBeforeOpeningItsFile() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 0, true, 1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
        verify(context, never()).commit();
    }

    @Test
    public void rejectsDistinctStoresUsingSameDirectory() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        destination.setBaseDir(new File(source.getBaseDir(), "."));

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 1, true, 1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
    }

    @Test
    public void rejectsSymbolicLinkToSourceDirectory() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        File alias = new File(temporaryFolder.getRoot(), "source-link");
        Files.createSymbolicLink(alias.toPath(), source.getBaseDir().toPath());
        destination.setBaseDir(alias);

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 1, true, 1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
    }

    @Test
    public void rejectsAliasedFileInsideDistinctDirectories() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        File destinationFile = destination.getFile(bitstream);
        Files.createDirectories(destinationFile.toPath().getParent());
        Files.createLink(destinationFile.toPath(), source.getFile(bitstream).toPath());

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 1, false, 1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
    }

    @Test
    public void rejectsUnconfiguredDestinationBeforeCopying() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 2, true, 1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
    }

    @Test
    public void rejectsNonpositiveBatchBeforeCopying() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);

        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 1, true, 0));
        assertThrows(IllegalArgumentException.class, () -> storage.migrate(context, 0, 1, true, -1));

        assertContent(source, bitstream);
        assertEquals(0, bitstream.getStoreNumber());
    }

    @Test
    public void copyFailureLeavesUncommittedSourceReadableAfterRollback() throws Exception {
        Bitstream first = bitstream("1234567890");
        Bitstream second = bitstream("9876543210");
        select(first, second);
        doThrow(new IOException("copy failed")).when(destination).put(eq(second), any(InputStream.class));

        assertThrows(IOException.class, () -> storage.migrate(context, 0, 1, true, 5));
        first.setStoreNumber(0);
        second.setStoreNumber(0);

        assertContent(source, first);
        assertContent(source, second);
        verify(context, never()).commit();
    }

    @Test
    public void commitFailureLeavesSourceReadableAfterRollback() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        doThrow(new SQLException("commit failed")).when(context).commit();

        assertThrows(SQLException.class, () -> storage.migrate(context, 0, 1, true, 1));
        bitstream.setStoreNumber(0);

        assertContent(source, bitstream);
        assertContent(destination, bitstream);
    }

    @Test
    public void closedContextCannotAuthorizeSourceDeletion() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        when(context.isValid()).thenReturn(false);

        assertThrows(SQLException.class, () -> storage.migrate(context, 0, 1, true, 1));

        assertContent(source, bitstream);
        verify(context, never()).commit();
    }

    @Test
    public void successfulBatchDeletesSourceOnlyAfterCommit() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);
        assertCopiesAtCommit(bitstream);

        storage.migrate(context, 0, 1, true, 1);

        verify(context).commit();
        assertFalse(source.getFile(bitstream).exists());
        assertContent(destination, bitstream);
        assertEquals(1, bitstream.getStoreNumber());
    }

    @Test
    public void finalPartialBatchCommitsBeforeDeletingSources() throws Exception {
        Bitstream first = bitstream("1234567890");
        Bitstream second = bitstream("9876543210");
        select(first, second);
        assertCopiesAtCommit(first, second);

        storage.migrate(context, 0, 1, true, 5);

        verify(context).commit();
        assertFalse(source.getFile(first).exists());
        assertFalse(source.getFile(second).exists());
        assertContent(destination, first);
        assertContent(destination, second);
    }

    @Test
    public void retainingSourcesLeavesPartialBatchCommitToCaller() throws Exception {
        Bitstream bitstream = bitstream("1234567890");
        select(bitstream);

        storage.migrate(context, 0, 1, false, 5);

        verify(context, never()).commit();
        assertContent(source, bitstream);
        assertContent(destination, bitstream);
        assertEquals(1, bitstream.getStoreNumber());
    }

    private DSBitStoreService store(File directory) {
        DSBitStoreService store = new DSBitStoreService();
        store.setBaseDir(directory);
        store.init();
        return store;
    }

    private Bitstream bitstream(String internalId) throws IOException {
        Bitstream bitstream = mock(Bitstream.class);
        AtomicInteger storeNumber = new AtomicInteger();
        when(bitstream.getInternalId()).thenReturn(internalId);
        when(bitstream.getStoreNumber()).thenAnswer(invocation -> storeNumber.get());
        doAnswer(invocation -> {
            storeNumber.set(invocation.getArgument(0));
            return null;
        }).when(bitstream).setStoreNumber(anyInt());
        source.put(bitstream, new ByteArrayInputStream(CONTENT));
        return bitstream;
    }

    private void select(Bitstream... bitstreams) throws SQLException {
        when(bitstreamService.findByStoreNumber(context, 0)).thenReturn(Arrays.asList(bitstreams).iterator());
    }

    private void assertCopiesAtCommit(Bitstream... bitstreams) throws SQLException {
        doAnswer(invocation -> {
            for (Bitstream bitstream : bitstreams) {
                assertContent(source, bitstream);
                assertContent(destination, bitstream);
                assertEquals(1, bitstream.getStoreNumber());
            }
            return null;
        }).when(context).commit();
    }

    private void assertContent(DSBitStoreService store, Bitstream bitstream) throws IOException {
        try (InputStream input = store.get(bitstream)) {
            assertArrayEquals(CONTENT, input.readAllBytes());
        }
    }
}
