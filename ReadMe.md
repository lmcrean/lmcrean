# Say Hi: [lmcrean@gmail.com](mailto:lmcrean@gmail.com)

# Open Source Contributions
Now running in production across millions of business applications.

## <img src="https://github.com/google.png" width="24" alt="Google"> Google

**Guava, Java**
*Google's core Java libraries used across millions of applications.*

1. **[Fix resource leak in FileBackedOutputStream to prevent file handle exhaustion](https://github.com/google/guava/pull/7986)**<br>*Fixed file handle exhaustion by adding proper exception handling to ensure FileOutputStream is closed when IOException occurs during memory-to-file transition.*
   <details><summary><code>+96/-1</code></summary>

   ```diff
   diff --git a/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java b/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   index 3cbf5a1028a7..ee7b43059187 100644
   --- a/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   +++ b/guava-tests/test/com/google/common/io/FileBackedOutputStreamTest.java
   @@ -171,4 +171,90 @@ private static boolean isAndroid() {
      private static boolean isWindows() {
        return OS_NAME.value().startsWith("Windows");
      }
   +
   +  /**
   +   * Test that verifies the resource leak fix for Issue #5756.
   +   *
   +   * This test covers a scenario where we write a smaller amount of data first,
   +   * then write a large amount that crosses the threshold (transitioning from
   +   * "not at threshold" to "over the threshold"). This differs from the existing
   +   * testThreshold() which writes exactly enough bytes to fill the buffer, then
   +   * immediately writes more bytes.
   +   *
   +   * Note: Direct testing of the IOException scenario during write/flush is challenging
   +   * without mocking. This test verifies that normal operation with threshold crossing
   +   * still works correctly with the fix in place.
   +   */
   +  public void testThresholdCrossing_ResourceManagement() throws Exception {
   +    // Test data that will cross the threshold
   +    int threshold = 50;
   +    byte[] beforeThreshold = newPreFilledByteArray(40);
   +    byte[] afterThreshold = newPreFilledByteArray(30);
   +
   +    FileBackedOutputStream out = new FileBackedOutputStream(threshold);
   +    ByteSource source = out.asByteSource();
   +
   +    // Write data that doesn't cross threshold
   +    out.write(beforeThreshold);
   +    assertNull(out.getFile());
   +
   +    // Write data that crosses threshold - this exercises the fixed code path
   +    if (!JAVA_IO_TMPDIR.value().equals("/sdcard")) {
   +      out.write(afterThreshold);
   +      File file = out.getFile();
   +      assertNotNull(file);
   +      assertTrue(file.exists());
   +
   +      // Verify all data was written correctly
   +      byte[] expected = new byte[70];
   +      System.arraycopy(beforeThreshold, 0, expected, 0, 40);
   +      System.arraycopy(afterThreshold, 0, expected, 40, 30);
   +      assertTrue(Arrays.equals(expected, source.read()));
   +
   +      // Clean up
   +      out.close();
   +      out.reset();
   +      assertFalse(file.exists());
   +    }
   +  }
   +
   +  /**
   +   * Test that verifies writes after crossing the threshold work correctly.
   +   *
   +   * Once the threshold is crossed, subsequent writes go to the file. This test
   +   * ensures that continued writing after the initial threshold crossing works
   +   * properly with the resource management fix in place.
   +   */
   +  public void testWriteAfterThresholdCrossing() throws Exception {
   +    // Use a small threshold to force multiple file operations
   +    int threshold = 10;
   +    FileBackedOutputStream out = new FileBackedOutputStream(threshold);
   +    ByteSource source = out.asByteSource();
   +
   +    // Write data in chunks: first below threshold, then crossing it, then after crossing
   +    byte[] chunk1 = newPreFilledByteArray(8);  // Below threshold
   +    byte[] chunk2 = newPreFilledByteArray(5);  // Crosses threshold
   +    byte[] chunk3 = newPreFilledByteArray(20); // More data to file
   +
   +    out.write(chunk1);
   +    assertNull(out.getFile());
   +
   +    if (!JAVA_IO_TMPDIR.value().equals("/sdcard")) {
   +      out.write(chunk2);
   +      File file = out.getFile();
   +      assertNotNull(file);
   +
   +      out.write(chunk3);
   +
   +      // Verify all data is correct
   +      byte[] expected = new byte[33];
   +      System.arraycopy(chunk1, 0, expected, 0, 8);
   +      System.arraycopy(chunk2, 0, expected, 8, 5);
   +      System.arraycopy(chunk3, 0, expected, 13, 20);
   +      assertTrue(Arrays.equals(expected, source.read()));
   +
   +      out.close();
   +      out.reset();
   +    }
   +  }
    }
   diff --git a/guava/src/com/google/common/io/FileBackedOutputStream.java b/guava/src/com/google/common/io/FileBackedOutputStream.java
   index ee7cc83c5d1d..4fe78aac11cd 100644
   --- a/guava/src/com/google/common/io/FileBackedOutputStream.java
   +++ b/guava/src/com/google/common/io/FileBackedOutputStream.java
   @@ -238,13 +238,22 @@ private void update(int len) throws IOException {
            // this is insurance.
            temp.deleteOnExit();
          }
   +      // Create and populate the file, ensuring proper resource management
   +      FileOutputStream transfer = null;
          try {
   -        FileOutputStream transfer = new FileOutputStream(temp);
   +        transfer = new FileOutputStream(temp);
            transfer.write(memory.getBuffer(), 0, memory.getCount());
            transfer.flush();
            // We've successfully transferred the data; switch to writing to file
            out = transfer;
          } catch (IOException e) {
   +        if (transfer != null) {
   +          try {
   +            transfer.close();
   +          } catch (IOException closeException) {
   +            e.addSuppressed(closeException);
   +          }
   +        }
            temp.delete();
            throw e;
          }
   ```
   </details>

2. **[Improve error messages for annotation methods on synthetic TypeVariables](https://github.com/google/guava/pull/7974)**<br>*Replaced unhelpful `UnsupportedOperationException("methodName")` with descriptive error messages explaining why annotations aren't supported on synthetic TypeVariables created by TypeResolver.*
   <details><summary><code>+19/-5</code></summary>

   ```diff
   diff --git a/guava/src/com/google/common/reflect/TypeResolver.java b/guava/src/com/google/common/reflect/TypeResolver.java
   index b28ffbb7228c..a69ddb80c23c 100644
   --- a/guava/src/com/google/common/reflect/TypeResolver.java
   +++ b/guava/src/com/google/common/reflect/TypeResolver.java
   @@ -368,10 +368,12 @@ Type resolveInternal(TypeVariable<?> var, TypeTable forDependants) {
             * by us. And that equality is guaranteed to hold because it doesn't involve the JDK
             * TypeVariable implementation at all.
             *
   -         * TODO: b/147144588 - But what about when the TypeVariable has annotations? Our
   -         * implementation currently doesn't support annotations _at all_. It could at least be made
   -         * to respond to queries about annotations by returning null/empty, but are there situations
   -         * in which it should return something else?
   +         * NOTE: b/147144588 - Custom TypeVariables created by Guava do not preserve annotations.
   +         * This is intentional. The semantics of annotation handling during type resolution are
   +         * unclear and have changed across Java versions. Until there's a clear specification for
   +         * what annotations should mean on resolved TypeVariables with modified bounds, annotation
   +         * methods will throw UnsupportedOperationException. Frameworks requiring annotation
   +         * preservation should use the original TypeVariable when bounds haven't changed.
             */
            if (Types.NativeTypeVariableEquals.NATIVE_TYPE_VARIABLE_ONLY
                && Arrays.equals(bounds, resolvedBounds)) {
   diff --git a/guava/src/com/google/common/reflect/Types.java b/guava/src/com/google/common/reflect/Types.java
   index 209369d017a4..57c3a3d51862 100644
   --- a/guava/src/com/google/common/reflect/Types.java
   +++ b/guava/src/com/google/common/reflect/Types.java
   @@ -382,7 +382,19 @@ private static final class TypeVariableInvocationHandler implements InvocationHa
          String methodName = method.getName();
          Method typeVariableMethod = typeVariableMethods.get(methodName);
          if (typeVariableMethod == null) {
   -        throw new UnsupportedOperationException(methodName);
   +        // Provide helpful error message for annotation-related methods
   +        if (methodName.equals("getAnnotatedBounds")
   +            || methodName.startsWith("getAnnotation")
   +            || methodName.startsWith("getDeclaredAnnotation")
   +            || methodName.equals("isAnnotationPresent")
   +            || methodName.equals("getAnnotations")
   +            || methodName.equals("getDeclaredAnnotations")) {
   +          throw new UnsupportedOperationException(
   +              "Annotation methods are not supported on synthetic TypeVariables created during type "
   +              + "resolution. The semantics of annotations on resolved types with modified bounds are "
   +              + "undefined. Use the original TypeVariable for annotation access. See b/147144588.");
   +        }
   +        throw new UnsupportedOperationException(methodName);  // Keep original behavior for other methods
          } else {
            try {
              return typeVariableMethod.invoke(typeVariableImpl, args);
   ```
   </details>

3. **[Fix `Iterators.mergeSorted()` to preserve stability for equal elements](https://github.com/google/guava/pull/7989)**<br>*Fixed unstable ordering of equal elements by tracking iterator insertion order and using it as a tiebreaker, ensuring elements from earlier iterators appear before equal elements from later ones.*
   <details><summary><code>+167/-10</code></summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   index c8bfdc84cfde..c1d2225718a7 100644
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   diff --git a/guava-tests/test/com/google/common/collect/IteratorsTest.java b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   index b1d09dbbe296..aa8b7cfff2ba 100644
   --- a/guava-tests/test/com/google/common/collect/IteratorsTest.java
   +++ b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   @@ -61,6 +61,7 @@
    import java.util.Arrays;
    import java.util.Collection;
    import java.util.Collections;
   +import java.util.Comparator;
    import java.util.ConcurrentModificationException;
    import java.util.Enumeration;
    import java.util.Iterator;
   @@ -68,6 +69,7 @@
    import java.util.List;
    import java.util.ListIterator;
    import java.util.NoSuchElementException;
   +import java.util.Objects;
    import java.util.RandomAccess;
    import java.util.Set;
    import java.util.Vector;
   @@ -1546,4 +1548,122 @@ public void testPeekingIteratorShortCircuit() {
        assertSame(peek, Iterators.peekingIterator(peek));
        assertSame(peek, Iterators.peekingIterator((Iterator<String>) peek));
      }
   +
   +  // Tests for demonstrating mergeSorted instability (Issue #5773)
   +  // These tests are expected to FAIL with the current implementation,
   +  // demonstrating that mergeSorted() is not stable for equal elements.
   +
   +  public void testMergeSorted_demonstratesInstability_issue5773Example() {
   +    List<TestDatum> left = ImmutableList.of(
   +        new TestDatum("B", 1),
   +        new TestDatum("C", 1)
   +    );
   +
   +    List<TestDatum> right = ImmutableList.of(
   +        new TestDatum("A", 2),
   +        new TestDatum("C", 2)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(left.iterator(), right.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +    assertEquals("First should be A2", "A", result.get(0).letter);
   +    assertEquals("First should be from right iterator", 2, result.get(0).number);
   +    assertEquals("Second should be B1", "B", result.get(1).letter);
   +    assertEquals("Second should be from left iterator", 1, result.get(1).number);
   +    assertEquals("Third should be C from left iterator (C1) for stability", 1, result.get(2).number);
   +    assertEquals("Fourth should be C from right iterator (C2) for stability", 2, result.get(3).number);
   +  }
   +
   +  public void testMergeSorted_demonstratesInstability_allEqual() {
   +    List<TestDatum> first = ImmutableList.of(
   +        new TestDatum("A", 1),
   +        new TestDatum("A", 2)
   +    );
   +
   +    List<TestDatum> second = ImmutableList.of(
   +        new TestDatum("A", 3),
   +        new TestDatum("A", 4)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(first.iterator(), second.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +    assertEquals("First should be A1 for stability", 1, result.get(0).number);
   +    assertEquals("Second should be A2 for stability", 2, result.get(1).number);
   +    assertEquals("Third should be A3 for stability", 3, result.get(2).number);
   +    assertEquals("Fourth should be A4 for stability", 4, result.get(3).number);
   +  }
   +
   +  private static class TestDatum {
   +    final String letter;
   +    final int number;
   +
   +    TestDatum(String letter, int number) {
   +      this.letter = letter;
   +      this.number = number;
   +    }
   +
   +    @Override
   +    public String toString() {
   +      return letter + number;
   +    }
   +
   +    @Override
   +    public boolean equals(Object o) {
   +      if (!(o instanceof TestDatum)) return false;
   +      TestDatum other = (TestDatum) o;
   +      return letter.equals(other.letter) && number == other.number;
   +    }
   +
   +    @Override
   +    public int hashCode() {
   +      return Objects.hash(letter, number);
   +    }
   +  }
    }
   diff --git a/guava/src/com/google/common/collect/Iterators.java b/guava/src/com/google/common/collect/Iterators.java
   index 0fa2cf03f674..94044bcb6a60 100644
   --- a/guava/src/com/google/common/collect/Iterators.java
   +++ b/guava/src/com/google/common/collect/Iterators.java
   @@ -1294,8 +1294,9 @@ public E peek() {
       * <p>Callers must ensure that the source {@code iterators} are in non-descending order as this
       * method does not sort its input.
       *
   -   * <p>For any equivalent elements across all {@code iterators}, it is undefined which element is
   -   * returned first.
   +   * <p>For any equivalent elements across all {@code iterators}, elements are returned in the order
   +   * of their source iterators. That is, if element A from iterator 1 and element B from iterator 2
   +   * compare as equal, A will be returned before B if iterator 1 was passed before iterator 2.
       *
       * @since 11.0
       */
   @@ -1318,22 +1319,43 @@ public E peek() {
       */
      private static final class MergingIterator<T extends @Nullable Object>
          extends UnmodifiableIterator<T> {
   -    final Queue<PeekingIterator<T>> queue;
   +
   +    private static class IndexedIterator<E extends @Nullable Object> {
   +      final PeekingIterator<E> iterator;
   +      final int index;
   +
   +      IndexedIterator(PeekingIterator<E> iterator, int index) {
   +        this.iterator = iterator;
   +        this.index = index;
   +      }
   +    }
   +
   +    final Queue<IndexedIterator<T>> queue;

        MergingIterator(
            Iterable<? extends Iterator<? extends T>> iterators, Comparator<? super T> itemComparator) {
   -      Comparator<PeekingIterator<T>> heapComparator =
   -          (PeekingIterator<T> o1, PeekingIterator<T> o2) ->
   -              itemComparator.compare(o1.peek(), o2.peek());
   +      Comparator<IndexedIterator<T>> heapComparator =
   +          (IndexedIterator<T> o1, IndexedIterator<T> o2) -> {
   +            int result = itemComparator.compare(o1.iterator.peek(), o2.iterator.peek());
   +            if (result == 0) {
   +              return Integer.compare(o1.index, o2.index);
   +            }
   +            return result;
   +          };

          queue = new PriorityQueue<>(2, heapComparator);

   +      int index = 0;
          for (Iterator<? extends T> iterator : iterators) {
            if (iterator.hasNext()) {
   -          queue.add(Iterators.peekingIterator(iterator));
   +          queue.add(
   +              new IndexedIterator<>(Iterators.peekingIterator(iterator), index));
            }
   +        index++;
          }
        }

   @@ -1345,10 +1367,11 @@ public boolean hasNext() {
        @Override
        @ParametricNullness
        public T next() {
   -      PeekingIterator<T> nextIter = queue.remove();
   +      IndexedIterator<T> nextIndexed = queue.remove();
   +      PeekingIterator<T> nextIter = nextIndexed.iterator;
          T next = nextIter.next();
          if (nextIter.hasNext()) {
   -        queue.add(nextIter);
   +        queue.add(nextIndexed);
          }
          return next;
        }
   ```
   </details>

4. **[Add tests demonstrating `Iterators.mergeSorted()` instability](https://github.com/google/guava/pull/7988)**<br>*Added test cases demonstrating the instability problem in `Iterators.mergeSorted()` as requested by maintainers, verifying the bug exists before the fix PR.*
   <details><summary><code>+134/-0</code></summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   index c8bfdc84cfde..c1d2225718a7 100644
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   diff --git a/guava-tests/test/com/google/common/collect/IteratorsTest.java b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   index b1d09dbbe296..aa8b7cfff2ba 100644
   --- a/guava-tests/test/com/google/common/collect/IteratorsTest.java
   +++ b/guava-tests/test/com/google/common/collect/IteratorsTest.java
   @@ -61,6 +61,7 @@
    import java.util.Arrays;
    import java.util.Collection;
    import java.util.Collections;
   +import java.util.Comparator;
    import java.util.ConcurrentModificationException;
    import java.util.Enumeration;
    import java.util.Iterator;
   @@ -68,6 +69,7 @@
    import java.util.List;
    import java.util.ListIterator;
    import java.util.NoSuchElementException;
   +import java.util.Objects;
    import java.util.RandomAccess;
    import java.util.Set;
    import java.util.Vector;
   @@ -1546,4 +1548,122 @@ public void testPeekingIteratorShortCircuit() {
        assertSame(peek, Iterators.peekingIterator(peek));
        assertSame(peek, Iterators.peekingIterator((Iterator<String>) peek));
      }
   +
   +  // Tests for demonstrating mergeSorted instability (Issue #5773)
   +
   +  public void testMergeSorted_demonstratesInstability_issue5773Example() {
   +    List<TestDatum> left = ImmutableList.of(
   +        new TestDatum("B", 1),
   +        new TestDatum("C", 1)
   +    );
   +
   +    List<TestDatum> right = ImmutableList.of(
   +        new TestDatum("A", 2),
   +        new TestDatum("C", 2)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(left.iterator(), right.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A2, B1, C1, C2]
   +    // ACTUAL (unstable): Sometimes [A2, B1, C1, C2], sometimes [A2, B1, C2, C1]
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +    assertEquals("First should be A2", "A", result.get(0).letter);
   +    assertEquals("First should be from right iterator", 2, result.get(0).number);
   +    assertEquals("Second should be B1", "B", result.get(1).letter);
   +    assertEquals("Second should be from left iterator", 1, result.get(1).number);
   +
   +    // THIS IS THE KEY ASSERTION THAT WILL FAIL:
   +    assertEquals("Third should be C from left iterator (C1) for stability", 1, result.get(2).number);
   +    assertEquals("Fourth should be C from right iterator (C2) for stability", 2, result.get(3).number);
   +  }
   +
   +  public void testMergeSorted_demonstratesInstability_allEqual() {
   +    List<TestDatum> first = ImmutableList.of(
   +        new TestDatum("A", 1),
   +        new TestDatum("A", 2)
   +    );
   +
   +    List<TestDatum> second = ImmutableList.of(
   +        new TestDatum("A", 3),
   +        new TestDatum("A", 4)
   +    );
   +
   +    Comparator<TestDatum> comparator = Comparator.comparing(d -> d.letter);
   +    Iterator<TestDatum> merged = Iterators.mergeSorted(
   +        ImmutableList.of(first.iterator(), second.iterator()),
   +        comparator);
   +
   +    List<TestDatum> result = ImmutableList.copyOf(merged);
   +
   +    // EXPECTED (if stable): [A1, A2, A3, A4] - maintaining iterator order
   +    // ACTUAL (unstable): Order of elements is non-deterministic
   +
   +    assertEquals("Should have 4 elements", 4, result.size());
   +
   +    // These assertions will FAIL non-deterministically:
   +    assertEquals("First should be A1 for stability", 1, result.get(0).number);
   +    assertEquals("Second should be A2 for stability", 2, result.get(1).number);
   +    assertEquals("Third should be A3 for stability", 3, result.get(2).number);
   +    assertEquals("Fourth should be A4 for stability", 4, result.get(3).number);
   +  }
   +
   +  private static class TestDatum {
   +    final String letter;
   +    final int number;
   +
   +    TestDatum(String letter, int number) {
   +      this.letter = letter;
   +      this.number = number;
   +    }
   +
   +    @Override
   +    public String toString() {
   +      return letter + number;
   +    }
   +
   +    @Override
   +    public boolean equals(Object o) {
   +      if (!(o instanceof TestDatum)) return false;
   +      TestDatum other = (TestDatum) o;
   +      return letter.equals(other.letter) && number == other.number;
   +    }
   +
   +    @Override
   +    public int hashCode() {
   +      return Objects.hash(letter, number);
   +    }
   +  }
   +
   +  // Note: These tests are intentionally designed to FAIL with the current
   +  // implementation to demonstrate issue #5773. They will pass once the
   +  // stability fix is applied.
    }
   ```
   </details>

5. **[Add test for putIfAbsent to catch implementations that incorrectly ignore null values](https://github.com/google/guava/pull/7987)**<br>*Added test to verify `putIfAbsent` correctly replaces existing null values, catching non-compliant Map implementations that pass the test suite despite violating the JavaDoc specification.*
   <details><summary><code>+14/-0</code></summary>

   ```diff
   diff --git a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   index c8bfdc84cfde..c1d2225718a7 100644
   --- a/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   +++ b/guava-testlib/src/com/google/common/collect/testing/testers/MapPutIfAbsentTester.java
   @@ -125,4 +125,18 @@ public void testPut_nullValueSupported() {
            getMap().putIfAbsent(nullValueEntry.getKey(), nullValueEntry.getValue()));
        expectAdded(nullValueEntry);
      }
   +
   +  @MapFeature.Require({SUPPORTS_PUT, ALLOWS_NULL_VALUES})
   +  @CollectionSize.Require(absent = ZERO)
   +  public void testPutIfAbsent_replacesNullValue() {
   +    // First, put a null value for an existing key
   +    getMap().put(k0(), null);
   +    assertEquals("Map should contain null value", null, getMap().get(k0()));
   +
   +    // putIfAbsent should replace the null value with the new value
   +    assertNull(
   +        "putIfAbsent(existingKeyWithNullValue, value) should return null",
   +        getMap().putIfAbsent(k0(), v3()));
   +    assertEquals("Map should now contain the new value", v3(), getMap().get(k0()));
   +  }
    }
   ```
   </details>

## <img src="https://github.com/rropen.png" width="24" alt="Rolls-Royce"> Rolls-Royce

**terraform-provider-cscdm, Go**
*Terraform provider for managing CSC domain registrations and DNS.*

1. **[Fix: Add HTTP timeout to prevent Terraform from hanging indefinitely](https://github.com/rropen/terraform-provider-cscdm/pull/16)**<br>*Added 30-second HTTP request timeout to prevent the Terraform provider from hanging indefinitely when the CSC Domain Manager API accepts connections but doesn't respond.*
   <details><summary><code>+11/-8</code></summary>

   ```diff
   diff --git a/internal/cscdm/cscdm.go b/internal/cscdm/cscdm.go
   index 812162f..58885d7 100644
   --- a/internal/cscdm/cscdm.go
   +++ b/internal/cscdm/cscdm.go
   @@ -15,6 +15,7 @@ const (
    	CSC_DOMAIN_MANAGER_API_URL = "https://apis.cscglobal.com/dbs/api/v2/"
    	POLL_INTERVAL              = 5 * time.Second
    	FLUSH_IDLE_DURATION        = 5 * time.Second
   +	HTTP_REQUEST_TIMEOUT       = 30 * time.Second
    )

    type Client struct {
   @@ -36,14 +37,16 @@ type Client struct {
    }

    func (c *Client) Configure(apiKey string, apiToken string) {
   -	c.http = &http.Client{Transport: &util.HttpTransport{
   -		BaseUrl: CSC_DOMAIN_MANAGER_API_URL,
   -		Headers: map[string]string{
   -			"accept":        "application/json",
   -			"apikey":        apiKey,
   -			"Authorization": fmt.Sprintf("Bearer %s", apiToken),
   -		},
   -	}}
   +	c.http = &http.Client{
   +		Timeout: HTTP_REQUEST_TIMEOUT,
   +		Transport: &util.HttpTransport{
   +			BaseUrl: CSC_DOMAIN_MANAGER_API_URL,
   +			Headers: map[string]string{
   +				"accept":        "application/json",
   +				"apikey":        apiKey,
   +				"Authorization": fmt.Sprintf("Bearer %s", apiToken),
   +			},
   +		}}

    	c.returnChannels = make(map[string]chan *ZoneRecord)
    	c.errorChannels = make(map[string]chan error)
   ```
   </details>

2. **[Enhance(error handling): improve flush loop and trigger handling in cscdm](https://github.com/rropen/terraform-provider-cscdm/pull/9)**<br>*Replaced `sync.Cond` with buffered channels to fix goroutine leaks, added `sync.Once` to prevent panics, and enabled recovery from transient failures instead of permanent termination.*
   <details><summary><code>+483/-19</code></summary>

   ```diff
   diff --git a/internal/cscdm/cscdm.go b/internal/cscdm/cscdm.go
   index 4b28cc4..812162f 100644
   --- a/internal/cscdm/cscdm.go
   +++ b/internal/cscdm/cscdm.go
   @@ -26,8 +26,9 @@ type Client struct {
    	batchMutex          sync.Mutex
    	returnChannelsMutex sync.Mutex

   -	flushTrigger      *sync.Cond
   +	flushTrigger      chan struct{}
    	flushLoopStopChan chan struct{}
   +	stopOnce          sync.Once

    	zoneCache  map[string]*Zone
    	zoneGroup  singleflight.Group
   @@ -47,7 +48,7 @@ func (c *Client) Configure(apiKey string, apiToken string) {
    	c.returnChannels = make(map[string]chan *ZoneRecord)
    	c.errorChannels = make(map[string]chan error)

   -	c.flushTrigger = sync.NewCond(&sync.Mutex{})
   +	c.flushTrigger = make(chan struct{}, 1)
    	c.flushLoopStopChan = make(chan struct{})

    	c.zoneCache = make(map[string]*Zone)
   @@ -57,28 +58,24 @@ func (c *Client) Configure(apiKey string, apiToken string) {

    func (c *Client) flushLoop() {
    	for {
   -		triggerChan := make(chan struct{})
   -		go func() {
   -			c.flushTrigger.L.Lock()
   -			c.flushTrigger.Wait()
   -			c.flushTrigger.L.Unlock()
   -			close(triggerChan)
   -		}()
   -
    		flushTimer := time.NewTimer(FLUSH_IDLE_DURATION)

    		select {
   -		case <-triggerChan:
   +		case <-c.flushTrigger:
    			// Flush triggered; reset flush timer
    			flushTimer.Stop()
   -			continue
   +			// Drain the channel in case of multiple signals
   +			select {
   +			case <-c.flushTrigger:
   +			default:
   +			}
    		case <-flushTimer.C:
    			// Timer expired; flush queue
    			err := c.flush()

    			if err != nil {
   -				fmt.Fprintf(os.Stderr, "failed to flush queue: %s", err.Error())
   -				return
   +				fmt.Fprintf(os.Stderr, "failed to flush queue: %s\n", err.Error())
   +				// Continue - don't return/terminate
    			}
    		case <-c.flushLoopStopChan:
    			// Stop flush loop
   @@ -89,12 +86,15 @@ func (c *Client) flushLoop() {
    }

    func (c *Client) triggerFlush() {
   -	c.flushTrigger.L.Lock()
   -	defer c.flushTrigger.L.Unlock()
   -
   -	c.flushTrigger.Signal()
   +	// Non-blocking send - if channel full, trigger already pending
   +	select {
   +	case c.flushTrigger <- struct{}{}:
   +	default:
   +	}
    }

    func (c *Client) Stop() {
   -	close(c.flushLoopStopChan)
   +	c.stopOnce.Do(func() {
   +		close(c.flushLoopStopChan)
   +	})
    }
   ```
   </details>

## <img src="https://github.com/stripe.png" width="24" alt="Stripe"> Stripe

**stripe-go, Go**
*Official Go client library for the Stripe payments API.*

- **[Add context-aware logging interface and update logger usage](https://github.com/stripe/stripe-go/pull/2178)**<br>*Adds `ContextLeveledLoggerInterface` to enable distributed tracing integration. Backend checks interface type on each log call and passes context when supported. Fully backward compatible with existing `LeveledLoggerInterface` implementations. Fixes #1281.*
   <details><summary><code>+536/-19</code></summary>

   ```diff
   diff --git a/log.go b/log.go
   index b52d7ac56b..6f529a5db5 100644
   --- a/log.go
   +++ b/log.go
   @@ -1,6 +1,7 @@
    package stripe

    import (
   +	"context"
    	"fmt"
    	"io"
    	"os"
   @@ -140,3 +141,24 @@ type LeveledLoggerInterface interface {
    	// Warnf logs a warning message using Printf conventions.
    	Warnf(format string, v ...interface{})
    }
   +
   +// ContextLeveledLoggerInterface provides a context-aware leveled logging interface
   +// for printing debug, informational, warning, and error messages with access to
   +// the request's context.Context.
   +//
   +// This interface allows loggers to extract trace IDs, request IDs, and other
   +// contextual information for distributed tracing systems like OpenTelemetry,
   +// OpenCensus, or custom correlation tracking.
   +type ContextLeveledLoggerInterface interface {
   +	// Debugf logs a debug message using Printf conventions with context.
   +	Debugf(ctx context.Context, format string, v ...interface{})
   +
   +	// Errorf logs an error message using Printf conventions with context.
   +	Errorf(ctx context.Context, format string, v ...interface{})
   +
   +	// Infof logs an informational message using Printf conventions with context.
   +	Infof(ctx context.Context, format string, v ...interface{})
   +
   +	// Warnf logs a warning message using Printf conventions with context.
   +	Warnf(ctx context.Context, format string, v ...interface{})
   +}
   diff --git a/stripe.go b/stripe.go
   index f1a0111fb2..ee3334231f 100644
   --- a/stripe.go
   +++ b/stripe.go
   @@ -228,6 +228,11 @@ type BackendConfig struct {
    	// LeveledLogger is the logger that the backend will use to log errors,
    	// warnings, and informational messages.
    	//
   +	// This field accepts either LeveledLoggerInterface (the traditional interface)
   +	// or ContextLeveledLoggerInterface (the context-aware interface). The SDK will
   +	// automatically detect which interface your logger implements and use it
   +	// appropriately.
   +	//
    	// LeveledLoggerInterface is implemented by LeveledLogger, and one can be
    	// initialized at the desired level of logging.  LeveledLoggerInterface
    	// also provides out-of-the-box compatibility with a Logrus Logger, but may
   @@ -239,7 +244,7 @@ type BackendConfig struct {
    	// To set a logger that logs nothing, set this to a stripe.LeveledLogger
    	// with a Level of LevelNull (simply setting this field to nil will not
    	// work).
   -	LeveledLogger LeveledLoggerInterface
   +	LeveledLogger interface{}

    	// MaxNetworkRetries sets maximum number of times that the library will
    	// retry requests that appear to have failed due to an intermittent
   @@ -653,6 +662,42 @@ func (s *BackendImplementation) maybeEnqueueTelemetryMetrics(requestID string, r
    	}
    }

   +// logDebugf logs a debug message, using context-aware logger if available
   +func (s *BackendImplementation) logDebugf(ctx context.Context, format string, v ...interface{}) {
   +	if logger, ok := s.LeveledLogger.(ContextLeveledLoggerInterface); ok {
   +		logger.Debugf(ctx, format, v...)
   +	} else if logger, ok := s.LeveledLogger.(LeveledLoggerInterface); ok {
   +		logger.Debugf(format, v...)
   +	}
   +}
   +
   +// logInfof logs an info message, using context-aware logger if available
   +func (s *BackendImplementation) logInfof(ctx context.Context, format string, v ...interface{}) {
   +	if logger, ok := s.LeveledLogger.(ContextLeveledLoggerInterface); ok {
   +		logger.Infof(ctx, format, v...)
   +	} else if logger, ok := s.LeveledLogger.(LeveledLoggerInterface); ok {
   +		logger.Infof(format, v...)
   +	}
   +}
   +
   +// logWarnf logs a warning message, using context-aware logger if available
   +func (s *BackendImplementation) logWarnf(ctx context.Context, format string, v ...interface{}) {
   +	if logger, ok := s.LeveledLogger.(ContextLeveledLoggerInterface); ok {
   +		logger.Warnf(ctx, format, v...)
   +	} else if logger, ok := s.LeveledLogger.(LeveledLoggerInterface); ok {
   +		logger.Warnf(format, v...)
   +	}
   +}
   +
   +// logErrorf logs an error message, using context-aware logger if available
   +func (s *BackendImplementation) logErrorf(ctx context.Context, format string, v ...interface{}) {
   +	if logger, ok := s.LeveledLogger.(ContextLeveledLoggerInterface); ok {
   +		logger.Errorf(ctx, format, v...)
   +	} else if logger, ok := s.LeveledLogger.(LeveledLoggerInterface); ok {
   +		logger.Errorf(format, v...)
   +	}
   +}
   +
    func resetBodyReader(body *bytes.Buffer, req *http.Request) {
    	// This might look a little strange, but we set the request's body
    	// outside of `NewRequest` so that we can get a fresh version every
   ```
   </details>

**pg-schema-diff, Go**
*Tool for generating safe PostgreSQL schema migrations by diffing schemas.*

- **[Fix: Support `GENERATED ALWAYS AS` columns to reduce migration failures](https://github.com/stripe/pg-schema-diff/pull/232)**<br>*Fixed migration failures where generated columns were incorrectly treated as DEFAULT columns. Updated schema introspection to detect `pg_attribute.attgenerated`, extended the Column model, and fixed DDL generation to output proper `GENERATED ALWAYS AS ... STORED` syntax.*
   <details><summary><code>+275/-37</code></summary>

   ```diff
   diff --git a/internal/migration_acceptance_tests/column_cases_test.go b/internal/migration_acceptance_tests/column_cases_test.go
   index 19e3852..a6c16c6 100644
   --- a/internal/migration_acceptance_tests/column_cases_test.go
   +++ b/internal/migration_acceptance_tests/column_cases_test.go
   @@ -1184,6 +1184,149 @@ var columnAcceptanceTestCases = []acceptanceTestCase{
    			`,
    		},
    	},
   +	{
   +		name: "Add generated column",
   +		oldSchemaDDL: []string{
   +			`
               CREATE TABLE tabs (
                   id SERIAL PRIMARY KEY,
                   title TEXT NOT NULL,
                   artist TEXT
               );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
               CREATE TABLE tabs (
                   id SERIAL PRIMARY KEY,
                   title TEXT NOT NULL,
                   artist TEXT,
                   search_vector tsvector GENERATED ALWAYS AS (
                       to_tsvector('simple', title || ' ' || coalesce(artist, ''))
                   ) STORED
               );
   +			`,
   +		},
   +	},
   +	{
   +		name: "Drop generated column",
   +		oldSchemaDDL: []string{
   +			`
               CREATE TABLE tabs (
                   id SERIAL PRIMARY KEY,
                   title TEXT NOT NULL,
                   artist TEXT,
                   search_vector tsvector GENERATED ALWAYS AS (
                       to_tsvector('simple', title || ' ' || coalesce(artist, ''))
                   ) STORED
               );
   +			`,
   +		},
   +		newSchemaDDL: []string{
   +			`
               CREATE TABLE tabs (
                   id SERIAL PRIMARY KEY,
                   title TEXT NOT NULL,
                   artist TEXT
               );
   +			`,
   +		},
   +		expectedHazardTypes: []diff.MigrationHazardType{
   +			diff.MigrationHazardTypeDeletesData,
   +		},
   +	},
   +	// ... more test cases
    }
   diff --git a/internal/queries/queries.sql b/internal/queries/queries.sql
   index 5889b65..bc0c734 100644
   --- a/internal/queries/queries.sql
   +++ b/internal/queries/queries.sql
   @@ -89,11 +89,6 @@ WITH identity_col_seq AS (

    SELECT
        a.attname::TEXT AS column_name,
   -    COALESCE(coll.collname, '')::TEXT AS collation_name,
   -    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   -    COALESCE(
   -        pg_catalog.pg_get_expr(d.adbin, d.adrelid), ''
   -    )::TEXT AS default_value,
        a.attnotnull AS is_not_null,
        a.attlen AS column_size,
        a.attidentity::TEXT AS identity_type,
   @@ -103,6 +98,22 @@ SELECT
        identity_col_seq.seqmin AS min_value,
        identity_col_seq.seqcache AS cache_size,
        identity_col_seq.seqcycle AS is_cycle,
   +    COALESCE(coll.collname, '')::TEXT AS collation_name,
   +    COALESCE(collation_namespace.nspname, '')::TEXT AS collation_schema_name,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's' THEN ''
   +            ELSE pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +        END, ''
   +    )::TEXT AS default_value,
   +    COALESCE(
   +        CASE
   +            WHEN a.attgenerated = 's'
   +                THEN pg_catalog.pg_get_expr(d.adbin, d.adrelid)
   +            ELSE ''
   +        END, ''
   +    )::TEXT AS generation_expression,
   +    (a.attgenerated = 's') AS is_generated,
        pg_catalog.format_type(a.atttypid, a.atttypmod) AS column_type
    FROM pg_catalog.pg_attribute AS a
   diff --git a/internal/schema/schema.go b/internal/schema/schema.go
   index 3f8b294..33cdc3a 100644
   --- a/internal/schema/schema.go
   +++ b/internal/schema/schema.go
   @@ -264,8 +264,16 @@ type (
    		//   ''::text
    		//   CURRENT_TIMESTAMP
    		// If empty, indicates that there is no default value.
   -		Default    string
   -		IsNullable bool
   +		Default string
   +		// If the column is a generated column, this will be true.
   +		IsGenerated bool
   +		// If the column is a generated column, this will be the generation expression.
   +		// Examples:
   +		//   to_tsvector('simple', title || ' ' || coalesce(artist, ''))
   +		//   (price * 1.1)
   +		// Only populated if IsGenerated is true.
   +		GenerationExpression string
   +		IsNullable           bool
   diff --git a/pkg/diff/sql_generator.go b/pkg/diff/sql_generator.go
   index 54d8ef1..40228a6 100644
   --- a/pkg/diff/sql_generator.go
   +++ b/pkg/diff/sql_generator.go
   @@ -2637,12 +2637,14 @@ func buildColumnDefinition(column schema.Column) (string, error) {
    	if column.IsCollated() {
    		sb.WriteString(fmt.Sprintf(" COLLATE %s", column.Collation.GetFQEscapedName()))
    	}
   +	if column.IsGenerated {
   +		sb.WriteString(fmt.Sprintf(" GENERATED ALWAYS AS (%s) STORED", column.GenerationExpression))
   +	} else if len(column.Default) > 0 {
   +		sb.WriteString(fmt.Sprintf(" DEFAULT %s", column.Default))
   +	}
    	if !column.IsNullable {
    		sb.WriteString(" NOT NULL")
    	}
   -	if len(column.Default) > 0 {
   -		sb.WriteString(fmt.Sprintf(" DEFAULT %s", column.Default))
   -	}
   ```
   </details>

## <img src="https://github.com/gocardless.png" width="24" alt="GoCardless"> GoCardless

**woocommerce-gateway, PHP**
*Payment gateway plugin connecting WooCommerce stores to GoCardless Direct Debit.*

- **[Fix inconsistent subscription status after cancellation with centralized cancellation logic](https://github.com/gocardless/woocommerce-gateway-gocardless/pull/88)**<br>*Fixed subscription status incorrectly showing "Pending Cancellation" instead of "Cancelled" when users cancel before GoCardless payment confirmation. Added centralized cancellation handling with parent order status synchronization.*
   <details><summary><code>+81/-0</code></summary>

   ```diff
   diff --git a/includes/class-wc-gocardless-gateway-addons.php b/includes/class-wc-gocardless-gateway-addons.php
   index e490cb7..4c93110 100644
   --- a/includes/class-wc-gocardless-gateway-addons.php
   +++ b/includes/class-wc-gocardless-gateway-addons.php
   @@ -33,6 +33,9 @@ public function __construct() {
    			// Cancel in-progress payment on subscription cancellation.
    			add_action( 'woocommerce_subscription_pending-cancel_' . $this->id, array( $this, 'maybe_cancel_subscription_payment' ) );
    			add_action( 'woocommerce_subscription_cancelled_' . $this->id, array( $this, 'maybe_cancel_subscription_payment' ) );
   +
   +			// Status synchronization for parent orders.
   +			add_action( 'woocommerce_subscription_status_updated', array( $this, 'sync_parent_order_status' ), 10, 3 );
    		}

    		if ( class_exists( 'WC_Pre_Orders_Order' ) ) {
   @@ -40,6 +43,84 @@ public function __construct() {
    		}
    	}

   +	/**
   +	 * Synchronize parent order status when all subscriptions are cancelled.
   +	 * Also intercepts pending-cancel transitions for subscriptions with unconfirmed payments,
   +	 * checking the most recent order (parent or renewal) to determine if payment is confirmed.
   +	 *
   +	 * @since x.x.x
   +	 * @param WC_Subscription $subscription The subscription object.
   +	 * @param string          $new_status   The new subscription status.
   +	 * @param string          $old_status   The old subscription status.
   +	 */
   +	public function sync_parent_order_status( $subscription, $new_status, $old_status ) {
   +		// Only process GoCardless subscriptions and subscription cancellation triggered by the customer.
   +		if ( $this->id !== $subscription->get_payment_method() || ! isset( $_GET['change_subscription_to'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
   +			return;
   +		}
   +
   +		// Only process Some status -> 'pending-cancel' transition.
   +		if ( 'pending-cancel' !== $new_status || 'pending-cancel' === $old_status ) {
   +			return;
   +		}
   +
   +		/*
   +		 * Handle transition to pending-cancel status for unconfirmed payments.
   +		 * This checks the most recent order's payment status (parent or latest renewal) from the
   +		 * GoCardless API to avoid edge cases with webhook delays.
   +		 */
   +
   +		// Get the most recent order of the subscription.
   +		$last_order = is_callable( array( $subscription, 'get_last_order' ) )
   +			? $subscription->get_last_order( 'all' )
   +			: $subscription->get_parent();
   +
   +		// If the last order is not a valid order, return.
   +		if ( ! $last_order || ! is_a( $last_order, 'WC_Abstract_Order' ) ) {
   +			return;
   +		}
   +
   +		// Get payment status from GoCardless.
   +		$payment_id     = $this->get_order_resource( $last_order->get_id(), 'payment', 'id' );
   +		$payment_status = '';
   +
   +		if ( $payment_id ) {
   +			$payment = WC_GoCardless_API::get_payment( $payment_id );
   +
   +			if ( is_wp_error( $payment ) || empty( $payment['payments'] ) ) {
   +				wc_gocardless()->log(
   +					sprintf(
   +						'%s - Failed to retrieve payment for order #%s',
   +						__METHOD__,
   +						$last_order->get_id()
   +					)
   +				);
   +			} else {
   +				$payment_status = $payment['payments']['status'] ?? '';
   +			}
   +		}
   +
   +		// Payment confirmed statuses that indicate payment has gone through.
   +		$confirmed_statuses = array( 'confirmed', 'paid_out' );
   +
   +		// If payment is not confirmed, cancel immediately.
   +		if ( ! in_array( $payment_status, $confirmed_statuses, true ) ) {
   +			wc_gocardless()->log(
   +				sprintf(
   +					'%s - Cancelling subscription #%s immediately (order #%s has unconfirmed payment status: %s)',
   +					__METHOD__,
   +					$subscription->get_id(),
   +					$last_order->get_id(),
   +					$payment_status ? $payment_status : 'none'
   +				)
   +			);
   +			$subscription->update_status(
   +				'cancelled',
   +				__( 'Subscription cancelled immediately as payment not confirmed for the last order.', 'woocommerce-gateway-gocardless' )
   +			);
   +		}
   +	}
   +
    	/**
    	 * Update GoCardless resource in order meta.
    	 *
   ```
   </details>

## <img src="https://github.com/microsoft.png" width="24" alt="Microsoft"> Microsoft

**TypeAgent, TypeScript**
*Microsoft's AI agent framework for natural language task automation.*

- **[Return undefined instead of invalid action names for partial matches](https://github.com/microsoft/TypeAgent/pull/1478)**<br>*Prevented exceptions when typing partial cached commands by returning `undefined` instead of invalid "unknown.unknown" action names, enabling graceful handling of partial matches.*
   <details><summary><code>+10/-10</code></summary>

   ```diff
   diff --git a/ts/packages/cache/src/constructions/constructionValue.ts b/ts/packages/cache/src/constructions/constructionValue.ts
   index 0e5253918..f38ed2cf2 100644
   --- a/ts/packages/cache/src/constructions/constructionValue.ts
   +++ b/ts/packages/cache/src/constructions/constructionValue.ts
   @@ -184,7 +184,7 @@ export function createActionProps(

        if (actionProps === undefined) {
            if (partial) {
   -            return { fullActionName: "unknown.unknown" };
   +            return { fullActionName: undefined }; // Return undefined for partial matches
            }
            throw new Error(
                "Internal error: No values provided for action properties",
   @@ -194,19 +194,17 @@ export function createActionProps(
        if (Array.isArray(actionProps)) {
            actionProps.forEach((actionProp) => {
                if (actionProp.fullActionName === undefined) {
   -                if (partial) {
   -                    actionProp.fullActionName = "unknown.unknown";
   -                } else {
   +                if (!partial) {
                        throw new Error("Internal error: fullActionName missing");
                    }
   +                // Leave undefined for partial matches
                }
            });
        } else if (actionProps.fullActionName === undefined) {
   -        if (partial) {
   -            actionProps.fullActionName = "unknown.unknown";
   -        } else {
   +        if (!partial) {
                throw new Error("Internal error: fullActionName missing");
            }
   +        // Leave undefined for partial matches
        }

        return actionProps;
   diff --git a/ts/packages/cache/src/explanation/requestAction.ts b/ts/packages/cache/src/explanation/requestAction.ts
   index 14560c99d..a5f26eba3 100644
   --- a/ts/packages/cache/src/explanation/requestAction.ts
   +++ b/ts/packages/cache/src/explanation/requestAction.ts
   @@ -194,9 +194,11 @@ function executableActionsToString(actions: ExecutableAction[]): string {
    }

    function fromJsonAction(actionJSON: JSONAction) {
   -    const { schemaName, actionName } = parseFullActionNameParts(
   -        actionJSON.fullActionName,
   -    );
   +    const { schemaName, actionName } =
   +        actionJSON.fullActionName !== undefined
   +            ? parseFullActionNameParts(actionJSON.fullActionName)
   +            : { schemaName: undefined as any, actionName: undefined as any };
   +
        return createExecutableAction(
            schemaName,
            actionName,
   ```
   </details>

## <img src="https://github.com/penpot.png" width="24" alt="Penpot"> Penpot

**penpot, Clojure and SQL**
*Open-source design and prototyping platform (alternative to Figma).*

<img src="screenshots/penpot.png" width="200" alt="Penpot milestone lock feature">

- **[✨ Enhance (version control): Add milestone lock feature to prevent accidental deletion and bad actor interventions](https://github.com/penpot/penpot/pull/6982)**<br>*Implemented version locking system allowing users to protect saved milestones from accidental deletion or bad actors. Added database migration, RPC endpoints with authorization, and UI with visual lock indicators.*
   <details><summary><code>+292/-17</code></summary>

   ```diff
   diff --git a/backend/src/app/migrations.clj b/backend/src/app/migrations.clj
   index 795a9bea5c1..9c40bc884ce 100644
   --- a/backend/src/app/migrations.clj
   +++ b/backend/src/app/migrations.clj
   @@ -438,7 +438,10 @@
        {:name "0139-mod-file-change-table.sql"
   -    :fn (mg/resource "app/migrations/sql/0139-mod-file-change-table.sql")}])
   +    :fn (mg/resource "app/migrations/sql/0139-mod-file-change-table.sql")}
   +
   +   {:name "0140-add-locked-by-column-to-file-change-table"
   +    :fn (mg/resource "app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql")}])

   diff --git a/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql b/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql
   new file mode 100644
   index 00000000000..d9052b105fe
   --- /dev/null
   +++ b/backend/src/app/migrations/sql/0140-add-locked-by-column-to-file-change-table.sql
   @@ -0,0 +1,11 @@
   +-- Add locked_by column to file_change table for version locking feature
   +-- This allows users to lock their own saved versions to prevent deletion by others
   +
   +ALTER TABLE file_change
   +  ADD COLUMN locked_by uuid NULL REFERENCES profile(id) ON DELETE SET NULL DEFERRABLE;
   +
   +-- Create index for locked versions queries
   +CREATE INDEX file_change__locked_by__idx ON file_change (locked_by) WHERE locked_by IS NOT NULL;
   +
   +-- Add comment for documentation
   +COMMENT ON COLUMN file_change.locked_by IS 'Profile ID of user who has locked this version.';

   diff --git a/backend/src/app/rpc/commands/files_snapshot.clj b/backend/src/app/rpc/commands/files_snapshot.clj
   index 71689560a51..32c128af2bf 100644
   --- a/backend/src/app/rpc/commands/files_snapshot.clj
   +++ b/backend/src/app/rpc/commands/files_snapshot.clj
   @@ -29,7 +29,7 @@

    (def sql:get-file-snapshots
      "WITH changes AS (
   -      SELECT id, label, revn, created_at, created_by, profile_id
   +      SELECT id, label, revn, created_at, created_by, profile_id, locked_by
          FROM file_change
          WHERE file_id = ?
            AND data IS NOT NULL

   +;;; Lock/unlock version endpoints
   +
   +(defn- lock-file-snapshot!
   +  [conn snapshot-id profile-id]
   +  (db/update! conn :file-change
   +              {:locked-by profile-id}
   +              {:id snapshot-id}
   +              {::db/return-keys false})
   +  nil)
   +
   +(sv/defmethod ::lock-file-snapshot
   +  {::doc/added "1.20"
   +   ::sm/params schema:lock-file-snapshot}
   +  [cfg {:keys [::rpc/profile-id id]}]
   +  (db/tx-run! cfg
   +              (fn [{:keys [::db/conn]}]
   +                (let [snapshot (get-snapshot conn id)]
   +                  (files/check-edition-permissions! conn profile-id (:file-id snapshot))
   +
   +                  ;; Only the creator can lock their own version
   +                  (when (not= (:profile-id snapshot) profile-id)
   +                    (ex/raise :type :validation
   +                              :code :only-creator-can-lock
   +                              :hint "Only the version creator can lock it"))
   +
   +                  (lock-file-snapshot! conn id profile-id)))))
   +
   +(sv/defmethod ::unlock-file-snapshot
   +  {::doc/added "1.20"
   +   ::sm/params schema:unlock-file-snapshot}
   +  [cfg {:keys [::rpc/profile-id id]}]
   +  (db/tx-run! cfg
   +              (fn [{:keys [::db/conn]}]
   +                (let [snapshot (get-snapshot conn id)]
   +                  (files/check-edition-permissions! conn profile-id (:file-id snapshot))
   +
   +                  ;; Only the creator can unlock their own version
   +                  (when (not= (:profile-id snapshot) profile-id)
   +                    (ex/raise :type :validation
   +                              :code :only-creator-can-unlock
   +                              :hint "Only the version creator can unlock it"))
   +
   +                  (unlock-file-snapshot! conn id)))))

   diff --git a/frontend/src/app/main/data/workspace/versions.cljs b/frontend/src/app/main/data/workspace/versions.cljs
   index f2ae3bb3a70..d38d9b195e6 100644
   --- a/frontend/src/app/main/data/workspace/versions.cljs
   +++ b/frontend/src/app/main/data/workspace/versions.cljs
   @@ -148,6 +148,29 @@

   +(defn lock-version
   +  [id]
   +  (assert (uuid? id) "expected valid uuid for `id`")
   +  (ptk/reify ::lock-version
   +    ptk/WatchEvent
   +    (watch [_ _ _]
   +      (->> (rp/cmd! :lock-file-snapshot {:id id})
   +           (rx/map fetch-versions)))))
   +
   +(defn unlock-version
   +  [id]
   +  (assert (uuid? id) "expected valid uuid for `id`")
   +  (ptk/reify ::unlock-version
   +    ptk/WatchEvent
   +    (watch [_ _ _]
   +      (->> (rp/cmd! :unlock-file-snapshot {:id id})
   +           (rx/map fetch-versions)))))

   diff --git a/frontend/src/app/main/ui/ds/product/user_milestone.cljs b/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   --- a/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   +++ b/frontend/src/app/main/ui/ds/product/user_milestone.cljs
   @@ -25,6 +26,7 @@
       [:class {:optional true} :string]
       [:active {:optional true} :boolean]
       [:editing {:optional true} :boolean]
   +   [:locked {:optional true} :boolean]
       [:user
        [:map
         [:name {:optional true} [:maybe :string]]

   +       [:div {:class (stl/css :name-wrapper)}
   +        [:> text*  {:as "span" :typography t/body-small :class (stl/css :name)} label]
   +        (when locked
   +          [:> i/icon* {:icon-id i/lock :class (stl/css :lock-icon)}])])

   diff --git a/frontend/translations/en.po b/frontend/translations/en.po
   +msgid "labels.lock"
   +msgstr "Lock"
   +
   +msgid "labels.unlock"
   +msgstr "Unlock"
   +
   +msgid "errors.version-locked"
   +msgstr "This version is locked and cannot be deleted by others"
   +
   +msgid "errors.only-creator-can-lock"
   +msgstr "Only the version creator can lock it"
   ```
   </details>

# Developer Projects
My favourite Personal Projects 👇🏼
