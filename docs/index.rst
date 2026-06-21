sentinel-core
=============

Zero-dependency async network security and encryption library for Python.

.. toctree::
   :maxdepth: 2

   crypto
   network
   logger

Kurulum
-------

.. code-block:: bash

   pip install sentinel-core

Hızlı Başlangıç
---------------

.. code-block:: python

   from sentinel_core import xor_encrypt, xor_decrypt, DataMasker
   from sentinel_core import SentinelClient, get_logger

   # Şifreleme
   enc = xor_encrypt("gizli veri", "anahtar")
   dec = xor_decrypt(enc, "anahtar")

   # Logger
   log = get_logger("myapp")
   log.info("Başladı", extra={"port": 9000})

   # Async client
   import asyncio

   async def main():
       async with SentinelClient("127.0.0.1", 9000) as client:
           response = await client.send(b"merhaba")

   asyncio.run(main())
